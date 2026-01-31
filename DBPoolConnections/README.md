1️⃣ TCP 3-way handshake
   → connection established

2️⃣ Client sends DB query
   → 1 request

3️⃣ DB sends result
   → 1 response

4️⃣ TCP connection close
   → FIN / ACK (often simplified as 2-way)

---------------
Excercise:
 - Implement a simple connection pool using bounded Blocking Queue
 - make it threadsafe
  