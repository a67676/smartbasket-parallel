---- the command output ----

PS C:\Users\Najah\OneDrive\المستندات\GitHub\smartbasket-parallel> python benchmark.py
CPU: Intel64 Family 6 Model 186 Stepping 2, GenuineIntel
Logical cores: 20
RAM: 15.7 GB
OS: Windows-11-10.0.26300-SP0
Python: 3.14.0
N=100, M=4, C=2000, seed=42, p=[1, 2, 4, 6, 8], repeats=5 (nosync 10), timer=time.perf_counter()
sequential   p=1  mean=0.5149s  correct=5/5
nosync       p=1  mean=1.1884s  correct=10/10
nosync       p=2  mean=2.8842s  correct=0/10
nosync       p=4  mean=9.1467s  correct=0/10
nosync       p=6  mean=9.8630s  correct=0/10
nosync       p=8  mean=10.7789s  correct=0/10
lock         p=1  mean=1.1255s  correct=5/5
lock         p=2  mean=2.7121s  correct=5/5
lock         p=4  mean=5.8255s  correct=5/5
lock         p=6  mean=6.3373s  correct=5/5
lock         p=8  mean=6.7679s  correct=5/5
lock_batched p=1  mean=0.7739s  correct=5/5
lock_batched p=2  mean=0.6908s  correct=5/5
lock_batched p=4  mean=0.8490s  correct=5/5
lock_batched p=6  mean=1.1598s  correct=5/5
lock_batched p=8  mean=1.5036s  correct=5/5
queue        p=1  mean=0.7816s  correct=5/5
queue        p=2  mean=0.6962s  correct=5/5
queue        p=4  mean=0.8838s  correct=5/5
queue        p=6  mean=1.1644s  correct=5/5
queue        p=8  mean=1.4335s  correct=5/5
mapreduce    p=1  mean=0.7558s  correct=5/5
mapreduce    p=2  mean=0.6737s  correct=5/5
mapreduce    p=4  mean=0.8678s  correct=5/5
mapreduce    p=6  mean=1.1655s  correct=5/5
mapreduce    p=8  mean=1.5291s  correct=5/5
Saved to results/benchmark.csv
