for testing after ai stream
```ffplay -fflags nobuffer -flags low_delay -probesize 100000 -analyzeduration 0 udp://127.0.0.1:55081```
for testing before ai stream
```ffplay -fflags nobuffer -flags low_delay -probesize 100000 -analyzeduration 0 udp://127.0.0.1:55080```
for starting stream aot localhost shell
```docker exec -it stream_operations python3 /app/scripts/after_llm_stream.py```

