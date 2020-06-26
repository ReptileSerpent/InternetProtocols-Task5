import socket
import ssl
import sys
import getpass
import random
from base64 import b64encode

def process_user_files():
	global letter_text
	try:
		letter_file = open("user_files/letter.txt", 'r')
		letter_text = letter_file.read()
		letter_file.close()
	except Exception as exception:
		print ("Failed to read \"user_files/letter.txt\"." + " Exception: " + str(exception))
		sys.exit()

	print ("Found user's letter")

	config_list = ""
	try:
		config_file = open("user_files/config.txt", 'r')
		config_list = config_file.readlines()
		config_file.close()
	except Exception as exception:
		print ("Failed to read \"user_files/config.txt\"." + " Exception: " + str(exception))
		sys.exit()

	print ("Parsed user's config")

	global from_address, to_addresses, subject, attachments
	from_address = config_list[0][5:].rstrip("\r\n")
	to_addresses = config_list[1][3:].rstrip("\r\n")
	subject = config_list[2][8:].rstrip("\r\n")
	attachments_locations = config_list[3][6:].rstrip("\r\n").split(",")

	for filename in attachments_locations:
		try:
			attachment_file = open(filename, "rb")
			attachments[filename] = b64encode(attachment_file.read()).decode()
			attachment_file.close()
		except Exception as exception:
			print ("Failed to read " + filename + "." + " Exception: " + str(exception))
			sys.exit()

	print ("Read files for attachments")


def communicate_with_server():
	smtp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	smtp_socket.settimeout(5)
	smtp_socket = ssl.wrap_socket(smtp_socket)
	smtp_socket.connect(('smtp.yandex.ru', 465))
	receive_from_server(smtp_socket)

	greet_the_server(smtp_socket)
	authenticate_to_the_server(smtp_socket)

	send_senders_address(smtp_socket)
	send_recipents_addresses(smtp_socket)

	send_data_command(smtp_socket)
	data_message = form_data_message(from_address, to_addresses, subject, letter_text, attachments)
	send_data_message(smtp_socket, data_message)
	
	send_quit_command(smtp_socket)

	print('Your message has been successfully sent')
	smtp_socket.close()

def send_to_server(smtp_socket, message):
	message += "\n"
	smtp_socket.send(message.encode())

def receive_from_server(smtp_socket):
	while True:
		lines = smtp_socket.recv(1024).decode().split("\n")
		#print(lines[-2])		# lines[-1] is ""
		try:
			if (lines[-2][3] == " "):
				reply_code = lines[-2][:3]
				return reply_code
		except IndexError:
			pass


def greet_the_server(smtp_socket):
	send_to_server(smtp_socket, 'EHLO smtp_client')
	reply_code = receive_from_server(smtp_socket)
	print("Greeted the server. Reply code: " + str(reply_code))

def authenticate_to_the_server(smtp_socket):
	send_to_server(smtp_socket, 'AUTH LOGIN')
	receive_from_server(smtp_socket)
	login = input("Login: ")
	send_to_server(smtp_socket, b64encode(bytes(login, "utf-8")).decode())
	receive_from_server(smtp_socket)
	
	password = getpass.getpass("Password: ")
	send_to_server(smtp_socket, b64encode(bytes(password, "utf-8")).decode())
	
	reply_code = receive_from_server(smtp_socket)
	if reply_code == "535":
		print ("Incorrect login and/or password. Reply code: " + str(reply_code))
		sys.exit()
	if reply_code[0] != "2":
		print ("A failure has occured. Reply code: " + str(reply_code))
		sys.exit()

	print("Authenticated successfully. Reply code: " + str(reply_code))

def send_senders_address(smtp_socket):
	global from_address

	send_to_server(smtp_socket, 'MAIL FROM: ' + from_address)
	reply_code = receive_from_server(smtp_socket)
	if reply_code[0] != "2":
		print ("Failure related to sender's address. Reply code: " + str(reply_code))
		sys.exit()

	print ("Sent the sender's address. Reply code: " + str(reply_code))

def send_recipents_addresses(smtp_socket):
	global to_addresses
	to_addresses_as_list = to_addresses.split(",")
	for entry in to_addresses_as_list:
		send_to_server(smtp_socket, 'RCPT TO: ' + entry)
		reply_code = receive_from_server(smtp_socket)
		if reply_code[0] != "2":
			print ("Failure related to recipent's address. Reply code: " + str(reply_code))
			print ("Offending recipent: " + entry)
			sys.exit()

	print ("Sent the recipents' addresses. Reply code: " + str(reply_code))
	
def send_data_command(smtp_socket):
	send_to_server(smtp_socket, 'DATA')
	reply_code = receive_from_server(smtp_socket)
	if reply_code[0] != "3":
		print ("Failure when telling the server we have data to send. Reply code: " + str(reply_code))
		sys.exit()

	print ("Told the server we have data to send. Reply code: " + str(reply_code))


def get_random_boundary():
	boundary_symbols = "1234567890qwertyuiopasdfghjklzxcvbnm"
	boundary = ""
	for i in range(32):
		boundary += boundary_symbols[random.randint(0, 35)]
	return boundary

def form_data_message(from_address, to_addresses, subject, data, attachments):
	boundary = get_random_boundary()
	data_in_base64 = b64encode(data.encode('utf8')).decode()

	to_addresses_without_comma = to_addresses.replace(",", "")

	subject = "=?utf-8?B?" + b64encode(subject.encode()).decode() + "?="

	message_header = "From: " + from_address + "\n\
To: " + to_addresses_without_comma + "\n\
Subject: " + subject + "\n\
Content-Type: multipart/mixed; boundary=" + boundary + "\n\
\n\
--" + boundary + "\n\
Content-Type: text/plain; charset=utf-8\n\
Content-transfer-encoding: base64\n\
\n\
" + data_in_base64 + "\n\
\n"

	message_attachments = []
	for file_name, file_contents in attachments.items():
		file_name = "=?utf-8?B?" + b64encode(file_name.encode()).decode() +"?="
		attachment ="--" + boundary + "\n\
Content-Disposition: attachment; filename=\"" + file_name + "\"\n\
Content-Type: application/octet-stream\n\
Content-Transfer-Encoding: base64\n\
\n\
" + file_contents + "\n\
\n"
		message_attachments.append(attachment)

	message_ending = "--" + boundary + "--\n\
.\n"

	print("Formed the message")

	return str.join("", ([message_header] + message_attachments + [message_ending]))

def send_data_message(smtp_socket, data_message):
	send_to_server(smtp_socket, data_message)
	reply_code = receive_from_server(smtp_socket)
	if reply_code[0] != "2":
		print ("Failed to send the letter's contents. Reply code: " + reply_code)
		sys.exit()

	print("Sent the data message")

def send_quit_command(smtp_socket):
	send_to_server(smtp_socket, 'QUIT')
	receive_from_server(smtp_socket)


letter_text = ""
from_address = ""
to_addresses = ""
subject = ""
attachments = {}

process_user_files()
communicate_with_server()
