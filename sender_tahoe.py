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

class TCPTahoe:
    def __init__(self):
        self.slowStart = True
        self.congestionAvoid = False

        self.sshThresh = SSH_THRESHOLD
        self.cwnd = INITIAL_WINDOW

        self.dupeACKS = 0
        self.lastACK = 0

    def handle_ACK(self, ack_position):
        # New ACK
        if ack_position > self.lastACK:
            if self.slowStart:
                self.cwnd += self.cwnd
                if self.cwnd >= self.sshThresh:
                    self.slowStart = False
                    self.congestionAvoid = True
            elif self.congestionAvoid:
                self.cwnd += MESSAGE_SIZE // self.cwnd  # Increment cwnd by 1 packet size per RTT

            self.lastACK = ack_position
            self.dupeACKS = 0

        # Duplicate ACK
        elif ack_position == self.lastACK:
            self.dupeACKS += 1
            if self.dupeACKS == DUPE_ACK_THRESHOLD:
                self.handle_fastRetransmit()

        return True

    def get_Window(self):
        return self.cwnd

    def handle_timeout(self):
        self.sshThresh = self.cwnd // 2
        self.cwnd = MESSAGE_SIZE
        self.slowStart = True
        self.congestionAvoid = False

    def handle_fastRetransmit(self):
        self.sshThresh = self.cwnd // 2
        self.cwnd = MESSAGE_SIZE
        self.slowStart = True
        self.congestionAvoid = False


# Read data from the file
with open('/Users/adrianrivera/Desktop/EEC 173A (ECS 152)/Project3/2024_congestion_control_ecs152a/docker/file.mp3', 'rb') as f:
    data = f.read()

# Statistics
total_packet_delay = 0
total_jitter = 0
packetCount = 0
previous_delay = None

# Troubleshooting
timeout_count = 0

# Window Tracking
base_position = 0  
next_position = 0  
in_flight = OrderedDict()
tcp = TCPTahoe()

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
    start_throughput = time()
    udp_socket.bind(("0.0.0.0", 5000))
    sent_empty = False
    
    while True:
        try:
            udp_socket.settimeout(TIMEOUT_DURATION)
            windowSize = tcp.get_Window()
            
            while (next_position - base_position) < windowSize and next_position < len(data):
                chunk = data[next_position:next_position + MESSAGE_SIZE]
                if not chunk:
                    break

                message = int.to_bytes(next_position, SEQ_ID_SIZE, byteorder='big', signed=True) + chunk
                udp_socket.sendto(message, ('localhost', 5001))
                in_flight[next_position] = (message, time())
                next_position += len(chunk)
            
            if next_position >= len(data) and not in_flight and not sent_empty:
                message = int.to_bytes(next_position, SEQ_ID_SIZE, byteorder='big', signed=True)
                udp_socket.sendto(message, ('localhost', 5001))
                sent_empty = True
                continue
            elif sent_empty and not in_flight:
                break
            
            try:
                ack, addr = udp_socket.recvfrom(PACKET_SIZE)
                ack_position = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
                
                if tcp.handle_ACK(ack_position):
                    acknowledged = []
                    for pos in in_flight.keys():
                        if pos < ack_position:
                            acknowledged.append(pos)
                            packet_end_time = time()
                            packet_delay = packet_end_time - in_flight[pos][1]
                            
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
                
                next_position = base_position
                
                if base_position in in_flight:
                    timeout_count += 1
                    print(f"Timeout: Resending packet from position {base_position}")
                    packet = in_flight[base_position][0]
                    udp_socket.sendto(packet, ('localhost', 5001))
                    in_flight[base_position] = (packet, current_time)
                    
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
        throughput = len(data) / (end_throughput - start_throughput)
        avg_packet_delay = total_packet_delay / packetCount
        avg_jitter = total_jitter / (packetCount - 1) if packetCount > 1 else 0
        metric = (0.2 * (throughput / 2000) + 0.1 / avg_jitter + 0.8 / avg_packet_delay) if avg_jitter > 0 else (0.2 * (throughput / 2000) + 0.8 / avg_packet_delay)

        print(f'Throughput: {round(throughput, 7)}')
        print(f'Average Per-Packet Delay: {round(avg_packet_delay, 7)}')
        print(f'Average Jitter: {round(avg_jitter, 7)}')
        print(f'Performance Metric: {round(metric, 7)}')
