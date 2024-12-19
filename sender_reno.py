import socket
from time import time
from collections import OrderedDict

# Constants
PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE
TIMEOUT_DURATION = 1
DUPE_ACK_THRESHOLD = 3
# Window = 1 packet, SSHThresh = 64 packets
INITIAL_WINDOW = MESSAGE_SIZE
SSH_THRESHOLD = 64 * MESSAGE_SIZE

class TCPReno:
    def __init__(self):
        self.slowStart = True
        self.congestionAvoid = False
        self.fastRecovery = False

        self.sshThresh = SSH_THRESHOLD
        self.cwnd = INITIAL_WINDOW

        self.dupeACKS = 0

        self.lastACK = 0
        self.recoveryACK = 0


    def handle_ACK(self, position):
        # New ACK
        if position > self.lastACK:
            if self.fastRecovery: #Work on this section
                if position >= self.recoveryACK:
                    self.cwnd = self.sshThresh
                    self.dupeACKS = 0
                    
                    self.fastRecovery = False
                    self.congestionAvoid = True
            elif self.slowStart:
                self.cwnd += self.cwnd
                if self.cwnd >= self.sshThresh:
                    self.slowStart = False
                    self.congestionAvoid = True
            elif self.congestionAvoid:
                self.cwnd += MESSAGE_SIZE // self.cwnd

            self.lastACK = position
            self.dupeACKS = 0
            

        # Dupe ACK
        elif position == self.lastACK:
            self.dupeACKS += 1

            if self.dupeACKS == DUPE_ACK_THRESHOLD:
                self.handle_fastRecovery()
            elif self.fastRecovery:
                self.cwnd += MESSAGE_SIZE

        return True
    
    def get_Window(self):
        return self.cwnd

    def handle_timeout(self):
        self.sshThresh = (self.cwnd) // 2
        self.cwnd = MESSAGE_SIZE

        self.fastRecovery = False
        self.slowStart = True
        self.congestionAvoid = False

    def handle_fastRecovery(self):
        self.sshThresh = (self.cwnd) // 2 
        #Make room for up to 3 dupes
        self.cwnd = self.sshThresh + (3 * MESSAGE_SIZE)
        self.recoveryACK = self.lastACK

        self.fastRecovery = True
        self.slowStart = False
        self.congestionAvoid = False
    

# Read data from the file
#with open('/Users/adrianrivera/Desktop/EEC 173A (ECS 152)/Project3/2024_congestion_control_ecs152a/docker/file.mp3', #'rb') as f:
#    data = f.read()
# For Calvin's VM
with open('/home/vboxuser/Downloads/Python-3.13.0/2024_congestion_control_ecs152a/docker/file.mp3', 'rb') as f:
    data = f.read()

# Statistics
total_packet_delay = 0
total_jitter = 0
packetCount = 0
previous_delay = None

#Troubleshooting
timeout_count = 0

# Window Tracking
base_position = 0  
next_position = 0  
# {position: (packet_data, send_time)}
in_flight = OrderedDict()
tcp = TCPReno()

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
    start_throughput = time()
    udp_socket.bind(("0.0.0.0", 5000))
    sent_empty = False
    
    while True:
        try:
            udp_socket.settimeout(TIMEOUT_DURATION)
            windowSize = tcp.get_Window()
            
            # Send packets while window isn't full and we have data to send
            while (next_position - base_position) < (windowSize) and next_position < len(data):
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
                if tcp.handle_ACK(ack_position):
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
                print("Timeout occurred. Resending from last acknowledged position...")
                tcp.handle_timeout()
                current_time = time()
                
                # Reset next_position to start sending from the last acknowledged position
                next_position = base_position
                
                # Only resend the first unacknowledged packet
                if base_position in in_flight:
                    timeout_count += 1
                    print(f"Timeout: Resending packet from position {base_position}")
                    packet = in_flight[base_position][0]
                    udp_socket.sendto(packet, ('localhost', 5001))
                    in_flight[base_position] = (packet, current_time)
                    
                # Implement exponential backoff for timeout duration
                udp_socket.settimeout(min(TIMEOUT_DURATION * 2, 4))  # Cap at 4 seconds


                    
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
        # Debugging
        # print(timeout_count)
