import socket
from time import time
from collections import OrderedDict

# Constants
PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE
TIMEOUT_DURATION = 2
WINDOW_SIZE = 100

# Read data from the file
with open('/home/vboxuser/Downloads/Python-3.13.0/2024_congestion_control_ecs152a/docker/file.mp3', 'rb') as f:
    data = f.read()

total_packet_delay = 0
total_jitter = 0
packetCount = 0
previous_delay = None

# Window tracking
base_position = 0  # First byte position in window
next_position = 0  # Next byte position to be sent
in_flight = OrderedDict()  # {position: (packet_data, send_time)}

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
    start_throughput = time()
    udp_socket.bind(("0.0.0.0", 5000))
    sent_empty = False
    
    while True:
        try:
            udp_socket.settimeout(TIMEOUT_DURATION)
            
            #First Window of packets reaches timeout, want to see if reducing # of initial packets helps
            capacity = WINDOW_SIZE * MESSAGE_SIZE
            if base_position == 0:
                capacity = capacity / 2
            
            # Send packets while window isn't full and we have data to send
            while (next_position - base_position) < (capacity) and next_position < len(data):
                chunk = data[next_position:next_position + MESSAGE_SIZE]
                if not chunk:
                    break
                    
                message = int.to_bytes(next_position, SEQ_ID_SIZE, byteorder='big', signed=True) + chunk
                
                udp_socket.sendto(message, ('localhost', 5001))
                in_flight[next_position] = (message, time())
                next_position += len(chunk)
            
            # Handle completion
            if next_position >= len(data) and not in_flight and not sent_empty:
                message = int.to_bytes(next_position, SEQ_ID_SIZE, byteorder='big', signed=True)
                udp_socket.sendto(message, ('localhost', 5001))
                sent_empty = True
                continue
            elif sent_empty and not in_flight:
                break
            
            # Wait for ACKs
            try:
                ack, addr = udp_socket.recvfrom(PACKET_SIZE)
                ack_position = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
                
                # Remove acknowledged packets
                acknowledged = []
                for pos in in_flight.keys():
                    if pos < ack_position:
                        acknowledged.append(pos)
                        packet_end_time = time()
                        packet_delay = packet_end_time - in_flight[pos][1]
                        
                        # Update statistics
                        total_packet_delay += packet_delay
                        packetCount += 1
                        
                        if previous_delay is not None:
                            jitter = abs(packet_delay - previous_delay)
                            total_jitter += jitter
                        previous_delay = packet_delay
                
                for pos in acknowledged:
                    del in_flight[pos]
                
                base_position = ack_position
                
            except socket.timeout:
                print(f"Timeout occurred. Resending all packets in window... ({base_position},{next_position})")
                current_time = time()
                # Resend all packets in the window
                for pos, (packet, _) in in_flight.items():
                    udp_socket.sendto(packet, ('localhost', 5001))
                    in_flight[pos] = (packet, current_time)
                    
        except Exception as e:
            print(f"Error occurred: {e}")
            break

    # Send FINACK
    try:
        finack = int.to_bytes(0, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
        udp_socket.sendto(finack, ('localhost', 5001))
    except Exception as e:
        print(f"Error sending FINACK: {e}")

    # Calculate and print statistics
    end_throughput = time()

    udp_socket.close()

    if packetCount > 0:
        # Calculate throughput (bytes per second)
        throughput = len(data) / (end_throughput - start_throughput)

        # Calculate average packet delay (seconds)
        avg_packet_delay = total_packet_delay / packetCount

        # Calculate average jitter (seconds)
        avg_jitter = total_jitter / (packetCount - 1) if packetCount > 1 else 0

        # Calculate performance metric
        if avg_jitter > 0:
            metric = 0.2 * (throughput / 2000) + 0.1 / avg_jitter + 0.8 / avg_packet_delay
        else:
            metric = 0.2 * (throughput / 2000) + 0.8 / avg_packet_delay

        print(f'Throughput: {round(throughput, 7)}')
        print(f'Average Per-Packet Delay: {round(avg_packet_delay, 7)}')
        print(f'Average Jitter: {round(avg_jitter, 7)}')
        print(f'Performance Metric: {round(metric, 7)}')

