import time
import tracemalloc
from extractor import extract_playlist_info

def run_benchmark():
    tracemalloc.start()
    start_time = time.time()
    
    # We can't really extract a live playlist in a stable benchmark without a mock,
    # but let's see how long the import and initial setup takes.
    
    time_taken = time.time() - start_time
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"Time taken: {time_taken:.3f}s")
    print(f"Memory Peak: {peak / 10**6:.2f} MB")

if __name__ == "__main__":
    run_benchmark()
