# Asks for far more than the container's memory limit, in chunks big enough
# that the kernel notices before Python does.
chunks = []
while True:
    chunks.append(bytearray(16 * 1024 * 1024))
