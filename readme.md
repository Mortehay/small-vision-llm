for testing after ai stream
```ffplay -fflags nobuffer -flags low_delay -probesize 100000 -analyzeduration 0 udp://127.0.0.1:55081```
for testing before ai stream
```ffplay -fflags nobuffer -flags low_delay -probesize 100000 -analyzeduration 0 udp://127.0.0.1:55080```



sudo sysctl -w net.core.rmem_max=10485760
sudo sysctl -w net.core.rmem_default=10485760

ffplay -fflags nobuffer -flags low_delay -probesize 32 -analyzeduration 0 udp://127.0.0.1:55081

for starting stream aot localhost shell
```docker exec -it stream_operations python3 /app/scripts/camera_test.py```
