# Uses no CPU at all, so only the wall clock outside the container can end it.
# Prints first: what a killed program had already written must survive.
import time

print("dang cho")
time.sleep(3600)
