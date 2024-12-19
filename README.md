# eec173a-peoject3
EEC 173A - Computer Networks Project 3

In this project, the goal was to implement the UDP sender in Python that will send data from the large file to the receiver in a series of packets, where the size of each packet is 1024 bytes. We implemented 5 variants of the sender that implement the following congestion control protocols: Stop-and-wait, fixed sliding window with size 100 packets, TCP Tahoe, and TCP Reno.

For each UDP sender, we measured and reported thr throughput size (size of transmitted data/time taken to send data) in the units of bytes per second and the average per-packet delay in the units of seconds. The goal is to maximize throughput while also minimizing the average per-packet delay and variation on the per-packet delay (i.e. jitter).

To evaluate the performance of our UDP sender, we computed the following metric: Metric = 0.2*(Throughput/2000) + (0.1/Average Jitter) + (0.8/Average delay per packet)
