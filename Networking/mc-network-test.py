import socket
import struct
import sys
import time
import argparse
"""
Author - Jonathan Steward
https://twitter.com/ggjono
Company - Techex
http://techex.co.uk/
https://twitter.com/TechexUK
https://twitter.com/techexlabs

**mc-network-test.py**
This tool is to support testing Multicast operation over a network
It can be used to verify existing Multicast (MC) traffic exists on a given MC address and port
It can also be used in a ping-pong setup with two instances running either side of a MC network to send and acknowledge MC traffic over the given network
"""


def parse_args():
    """
    Standard function to parse input args.
    :param:
        n/a
    :return:
        arguments - parser object where the dest vars can be referenced like .file or .streams
    """
    description = """
    This tool is to support testing Multicast operation over a network
    It can be used to verify existing Multicast (MC) traffic exists on a given MC address and port
    It can also be used in a ping-pong setup with two instances running either side of a MC network to send and acknowledge MC traffic over the given network
    """
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)
    address_help = "Use this argument to provide the multicast address on which to send traffic\nDefault address - 239.1.1.1\n "
    port_help = "Use this argument to provide the multicast port on which to send traffic\nDefault port - 10000\n "
    option_help = "use this argument to define which option you want to trigger, s/S == Send r/R == Receive e.g -o/--option R\n "
    ttl_help = "use this argument to define the ttl of the multicast traffic sent out\nDefault TTL is 20\n "
    timeout_help = "use this argument to define a timeout for receiving an ack to the Multicast traffic\nDefault timeout is 0.2s\n "
    parser.add_argument("-a", "--address", help=address_help, dest="address", default="239.1.1.1")
    parser.add_argument("-p", "--port", help=port_help, dest="port", default=10000, type=int)
    parser.add_argument("-o", "--option", help=option_help, dest="option", required=True)
    parser.add_argument("-ttl", help=ttl_help, dest="ttl", default=20, type=int)
    parser.add_argument("-t", "--timeout", help=timeout_help, dest="timeout", default=0.2, type=int)
    arguments = parser.parse_args()
    return arguments


def form_sock_send(timeout, ttl):
    """
    Function to form the Network socket to send Multicast traffic
    :param timeout: How long to keep open waiting for an ACK to the MC traffic
    :param ttl: The TTL value to set when sending MC traffic
    :return: Sock object ready for the send function
    """
    # Create the datagram socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Set a timeout so the socket does not block indefinitely when trying to receive data, default - 0.2
    # to receive data.
    sock.settimeout(timeout)

    # Set the time-to-live for messages to control number of L3 hops for traffic to propigate over default - 20.
    ttl = struct.pack('b', ttl)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    return sock


def form_sock_receive(group, port):
    """
    Function to create socket to receive MC traffic for a specific group on a specific port
    :param group: Multicast Group to receive traffic on
    :param port:  Port To receive traffic on, this should match the sending port
    :return:
    """
    server_address = ('', port)

    # Create the socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind to the server address
    sock.bind(server_address)
    # Tell the operating system to add the socket to the multicast group on all interfaces.
    group = socket.inet_aton(group)
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock


def mc_send(multicast_group, message, sock):
    """
    Function to send Multicast traffic from local host to the network based on a given MC group and port with a given text message
    :param multicast_group: MC Group to send traffic to
    :param message: Text to send out in the MC traffic
    :param sock: Socket object to use when sending traffic.
    :return: True/False based on if an Ack has been received or not.
    """
    received_ack = False
    try:
        # Send data to the multicast group
        print(sys.stderr, 'sending "%s"' % message)
        sock.sendto(message, multicast_group)

        # Look for responses from all recipients
        while True:
            print(sys.stderr, 'waiting to receive')
            try:
                data, server = sock.recvfrom(16)
            except socket.timeout:
                print(sys.stderr, 'timed out, no more responses')
                return received_ack
            else:
                print(sys.stderr, 'received "%s" from %s' % (data, server))
                received_ack = True
    except:
        print(sys.stderr, 'closing socket')
        sock.close()
        sys.exit()


def loop_sending_mc(group, port, timeout, ttl):
    """
    Function to loop sending MC traffic with ability to speed up or slow down based on if we receive acknowledgements
    :param group: Multicast group to send traffic to
    :param port: Port to send Multicast traffic on
    :param timeout: Timeout specifying how long to keep the port open waiting for an acknowledgement
    :param ttl: Time to live value set on the MC packet sent out onto the network. Defines #of L3 hops till packet dies
    :return:
    """
    multicast_group = (group, port)
    loop = True
    num_sent = 0
    message = 'very important data - {}'
    sleep = 2.0 #Default sleep for 2s for MC packets
    sock = form_sock_send(timeout, ttl)
    while loop:
        message_no = message.format(num_sent)
        message_bytes = str.encode(message_no)
        if mc_send(multicast_group, message_bytes, sock):
            sleep = sleep/2
            #Reduce the sleep value to support more/quicker received packets
        else:
            sleep = min(max(1.0, (sleep*2)), 10.0)
            #Doubling sleep period to a max value of 10 sec in case of no received ack's
            #Min to ensure we don't keep doubling to a stupid sleep value
            #Max to ensure after successful Ack's stop being recieved the script will set sleep to 1s by default
            #Otherwise script would not sleep at all when seeing failures after a success
        num_sent += 1
        if sleep >= 1:
            print("sleeping for {}s".format(sleep))
        time.sleep(sleep)
        print("sent {} MC packets so far".format(num_sent))


def receive_mc(group, port):
    """
    Function to receive multicast traffic on a local device and send back an acknowledgement to the sending device
    :param group: Multicast group to receive traffic on.
    :param port: Port to receive traffic on
    :return:
    """
    sock = form_sock_receive(group, port)

    # Receive/respond loop
    while True:
        print(sys.stderr, 'waiting to receive message')
        data, address = sock.recvfrom(1024)

        print(sys.stderr, 'received {} bytes from {}'.format(len(data), address))
        try:
            data_str = data.decode()
            packet_no = data_str.split("-")[1]
            print(sys.stderr, "message: {}".format(data_str))
            print(sys.stderr, 'sending acknowledgement {} to {}'.format(packet_no, address))
            sock.sendto(str.encode("ack - {}".format(packet_no)), address)
        except:
            print("Multicast data received isn't from the python mc-network-test.py sender!")
            print("Some other source on address '{}' is sending traffic! Sleeping for 5s".format(address))
            time.sleep(5)


args = parse_args() # Call Parse args to get CLI input

if args.option.lower() == "s":
    loop_sending_mc(args.address, args.port, args.timeout, args.ttl)
elif args.option.lower() == "r":
    receive_mc(args.address, args.port)
else:
    print("The wrong option was selected\nYou selected {}\nValid options are: s/S == Send r/R == Receive e.g -o/--option R")

