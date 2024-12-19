import socket
from time import time

# Constants
PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE
TIMEOUT_DURATION = 1  # Initial timeout duration for retries

# Read data from the file
with open('/Users/adrianrivera/Desktop/EEC 173A (ECS 152)/Project3/2024_congestion_control_ecs152a/docker/file.mp3', 'rb') as f:
    data = f.read()

total_packet_delay = 0
total_jitter = 0
packetCount = 0
previous_delay = None

# Create a UDP socket
start_throughput = time()
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:

    # Bind the socket to a local port
    udp_socket.bind(("0.0.0.0", 5000))

    seq_id = 0
    expected_ack = 0
    sent_empty = False

    while True:
        udp_socket.settimeout(TIMEOUT_DURATION)
        
        # Construct message: sequence id + data
        message = int.to_bytes(seq_id, SEQ_ID_SIZE, byteorder='big', signed=True) + data[seq_id: seq_id + MESSAGE_SIZE]

        # If all data has been sent, construct the empty packet to signal completion
        if seq_id >= len(data) and not sent_empty:
            message = int.to_bytes(len(data), SEQ_ID_SIZE, byteorder='big', signed=True)
            sent_empty = True
            expected_ack = seq_id
        else:
            chunk = data[seq_id:seq_id + MESSAGE_SIZE]
            message = int.to_bytes(seq_id, SEQ_ID_SIZE, byteorder='big', signed=True) + chunk
            expected_ack = seq_id + len(chunk)

        # Print statement for sending packet
        print(f"Sending packet {seq_id} (Size: {len(message)} bytes)")

        # Send message
        udp_socket.sendto(message, ('localhost', 5001))
        packet_delay_start = time()
        packetCount += 1
        
        ack_received = False
        ack_id = None
        while not ack_received:
            try:
                # Wait for ACK
                ack, _ = udp_socket.recvfrom(PACKET_SIZE)
                packet_delay_end = time()

                # Calculate delay for the current packet
                packet_delay = packet_delay_end - packet_delay_start
                total_packet_delay += packet_delay

                # Calculate jitter (difference with previous packet delay)
                if previous_delay is not None:
                    jitter = abs(packet_delay - previous_delay)
                    total_jitter += jitter

                # Store the current delay for jitter calculation in the next iteration
                previous_delay = packet_delay

                # Extract ACK ID
                ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)

                

                # If ACK is for the expected packet or final ACK, exit the loop
                if ack_id == expected_ack:
                    ack_received = True
                    print(f"ACK for packet {seq_id} received successfully!")
                else:
                    # Print statement for received ACK and expected seq_id
                    print(f"Expected ACK for packet {seq_id}, but received ACK for packet {ack_id}")

            except socket.timeout:
                # No ACK received, resend unacknowledged message
                print(f"Timeout waiting for ACK for packet {seq_id}. Resending...")
                udp_socket.settimeout(TIMEOUT_DURATION)
                udp_socket.sendto(message, ('localhost', 5001))

        # Check if final ACK received
        if ack_id == len(data):
            print("Received final ACK, closing transmission.")
            break

        # Move to next packet
        if not sent_empty:
            seq_id += MESSAGE_SIZE
            seq_id = min(seq_id, len(data))  # Ensure seq_id does not exceed data length

    # Measure throughput time until last data packet
    end_throughput = time()

    # Send final ACK
    finack = int.to_bytes(0, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    print("Sending final FINACK message.")
    udp_socket.sendto(finack, ('localhost', 5001))

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

    print(f'Throughput: {round(throughput, 2)}')
    print(f'Average Per-Packet Delay: {round(avg_packet_delay, 2)}')
    print(f'Average Jitter: {round(avg_jitter, 2)}')
    print(f'Performance Metric: {round(metric, 2)}')

    # Close the socket
    udp_socket.close()
