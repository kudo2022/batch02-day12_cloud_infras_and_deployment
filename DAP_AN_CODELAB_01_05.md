# Dap An Codelab 01 -> 05

Tai lieu nay tong hop dap an va ghi chu thuc te cho cac phan `01` den `05` trong repo `batch02-day12_cloud_infras_and_deployment`.

Minh uu tien viet theo dung code dang co trong repo nay, va neu co cho nao tai lieu goc lech voi code, minh ghi ro cach dung dung.

## 1. Localhost vs Production

### 1.1. Anti-patterns trong `01-localhost-vs-production/develop/app.py`

It nhat 5 van de:

1. `OPENAI_API_KEY` bi hardcode trong code.
2. `DATABASE_URL` bi hardcode trong code.
3. `DEBUG = True` bat cung.
4. Port bi cung o `8000`.
5. Bind `host="localhost"` nen khong phu hop khi chay trong container/cloud.
6. Khong co endpoint `/health`.
7. Khong co endpoint `/ready`.
8. Dung `print()` thay vi structured logging.
9. Log ca secret ra console: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`.
10. `reload=True` chi phu hop dev, khong phu hop production.

### 1.2. Cach chay ban develop

PowerShell:

```powershell
cd .\01-localhost-vs-production\develop
pip install -r requirements.txt
python app.py
```

Test dung cho code hien tai:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/ask?question=Hello" `
  -Method Post
```

Luu y: ban `develop` nhan `question` qua query string, khong nhan JSON body.

### 1.3. Cach chay ban production

PowerShell:

```powershell
cd .\01-localhost-vs-production\production
Copy-Item .env.example .env
pip install -r requirements.txt
python app.py
```

Test:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:8000/ready"
Invoke-RestMethod `
  -Uri "http://localhost:8000/ask" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"question":"Hello production"}'
```

### 1.4. So sanh develop vs production

| Feature | Develop | Production | Tai sao quan trong |
|---|---|---|---|
| Config | Hardcode | `config.py` doc tu env vars | De doi moi truong ma khong sua code |
| Secrets | Hardcode trong code | `OPENAI_API_KEY`, `AGENT_API_KEY` tu env | Tranh lo secret |
| Host/port | `localhost:8000` | `0.0.0.0` va `PORT` | Chay duoc trong container/cloud |
| Logging | `print()` | JSON logging | De collect log tren cloud |
| Health check | Khong co | `/health` | Platform biet service con song |
| Readiness | Khong co | `/ready` | Load balancer biet instance san sang |
| Shutdown | Dot ngot | Graceful qua lifespan + SIGTERM | Tranh rot request dang xu ly |

### 1.5. Checkpoint 1

- Hardcode secrets la nguy hiem vi de lo key neu push len GitHub.
- Env vars la cach dung de tach config khoi code.
- `/health` la liveness probe.
- `/ready` la readiness probe.
- Graceful shutdown la dung nhan request moi, cho request dang chay xong roi tat.

## 2. Docker

### 2.1. Dockerfile co ban trong `02-docker/develop/Dockerfile`

Tra loi cau hoi:

1. Base image: `python:3.11`
2. Working directory: `/app`
3. `COPY requirements.txt` truoc de Docker cache layer cai package. Neu code doi ma requirements khong doi, layer pip install duoc tai su dung.
4. `CMD` la lenh mac dinh khi container start. `ENTRYPOINT` dung khi muon co mot executable co dinh, con `CMD` thuong la default argument/default command.

### 2.2. Cach build va run dung cho repo nay

Quan trong: build tu thu muc goc repo, vi Dockerfile copy file theo duong dan tu root.

```powershell
cd D:\Lab_Vinuni\Day12_Deploy\batch02-day12_cloud_infras_and_deployment
docker build -f .\02-docker\develop\Dockerfile -t agent-develop .
docker run --rm -p 8000:8000 agent-develop
```

Test:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod `
  -Uri "http://localhost:8000/ask?question=What%20is%20Docker" `
  -Method Post
```

Luu y: ban `develop` cua phan Docker cung nhan `question` qua query string, khong nhan JSON body.

### 2.3. Multi-stage build trong `02-docker/production/Dockerfile`

Tra loi:

- Stage 1 `builder`: cai dependencies.
- Stage 2 `runtime`: chi copy nhung gi can de chay.
- Image nho hon vi khong mang theo build tools va cac layer khong can thiet cua giai doan build.

### 2.4. Docker Compose stack trong `02-docker/production/docker-compose.yml`

Architecture:

- `agent`: FastAPI app
- `redis`: cache/session/rate limit
- `qdrant`: vector database
- `nginx`: reverse proxy va load balancer

Giao tiep:

- `nginx` forward request vao `agent`
- `agent` noi vao `redis`
- `agent` noi vao `qdrant`

Lenh chay:

```powershell
docker compose -f .\02-docker\production\docker-compose.yml up
```

Test:

```powershell
Invoke-RestMethod -Uri "http://localhost/health"
Invoke-RestMethod `
  -Uri "http://localhost/ask" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"question":"Explain microservices"}'
```

Ghi chu repo:

- Minh da bo tham chieu `env_file` khong ton tai trong compose file.
- Minh da them `02-docker/production/requirements.txt` vi Dockerfile dang can file nay de build.

### 2.5. Checkpoint 2

- Hieu Dockerfile la script tao image.
- Hieu multi-stage giup image gon hon.
- Hieu Docker Compose dung de orchestration nhieu service.
- Debug co ban:

```powershell
docker logs <container-id>
docker exec -it <container-id> sh
docker ps
docker images
```

## 3. Cloud Deployment

Phan nay minh doi chieu theo config trong repo. Minh khong the deploy that tu may nay vi can tai khoan cloud, browser login, va secret ben ngoai.

### 3.1. Railway

File lien quan:

- `03-cloud-deployment/railway/app.py`
- `03-cloud-deployment/railway/railway.toml`

Y chinh:

- App doc `PORT` tu env var.
- Start command trong `railway.toml`:

```toml
startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"
```

- Health check path: `/health`

Lenh:

```powershell
cd .\03-cloud-deployment\railway
npm i -g @railway/cli
railway login
railway init
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key
railway up
railway domain
```

Test sau khi co domain:

```powershell
Invoke-RestMethod -Uri "https://<your-domain>/health"
Invoke-RestMethod `
  -Uri "https://<your-domain>/ask" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"question":"Am I on the cloud?"}'
```

### 3.2. Render

File lien quan:

- `03-cloud-deployment/render/render.yaml`

Y chinh:

- `runtime: python`
- `buildCommand: pip install -r requirements.txt`
- `startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT`
- `healthCheckPath: /health`
- Ho tro `redis` service kem theo

Khac Railway:

- Railway dung `railway.toml`
- Render dung `render.yaml`
- Render nghieng ve deploy tu GitHub + Blueprint

### 3.3. Cloud Run

File lien quan:

- `03-cloud-deployment/production-cloud-run/cloudbuild.yaml`
- `03-cloud-deployment/production-cloud-run/service.yaml`

Y chinh:

- `cloudbuild.yaml` mo ta pipeline test -> build -> push -> deploy
- `service.yaml` mo ta Cloud Run service, resource, health probe, env vars, secrets
- `minScale: 1` de tranh cold start

### 3.4. Checkpoint 3

De dat checkpoint 3:

- Can deploy thanh cong len it nhat 1 platform
- Co public URL
- Biet set env vars/secrets tren cloud
- Biet xem logs

Trang thai thuc te tren may nay:

- Config da duoc doc va doi chieu
- Chua deploy that vi thieu login/tai khoan cloud cua ban

## 4. API Gateway va Security

### 4.1. Ban develop: API key auth

File:

- `04-api-gateway/develop/app.py`

Tra loi:

- API key duoc check trong dependency `verify_api_key()`.
- Thieu key -> `401`.
- Sai key -> `403`.
- Rotate key = doi gia tri `AGENT_API_KEY` trong environment va restart service.

Chay:

```powershell
cd .\04-api-gateway\develop
$env:AGENT_API_KEY="secret-key-123"
python app.py
```

Test:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/ask?question=Hello" `
  -Method Post
```

Se bi `401`.

Dung key dung:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/ask?question=Hello" `
  -Method Post `
  -Headers @{ "X-API-Key" = "secret-key-123" }
```

### 4.2. Ban production: JWT

File:

- `04-api-gateway/production/app.py`
- `04-api-gateway/production/auth.py`

Flow:

1. `POST /auth/token` de lay JWT
2. Gui `Authorization: Bearer <token>` khi goi `/ask`
3. `verify_token()` giai ma va lay `username`, `role`

Demo credentials:

- `student / demo123` -> role `user`
- `teacher / teach456` -> role `admin`

Lenh:

```powershell
cd .\04-api-gateway\production
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Lay token:

```powershell
$token = (Invoke-RestMethod `
  -Uri "http://localhost:8000/auth/token" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"username":"student","password":"demo123"}').access_token
```

Goi API:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/ask" `
  -Method Post `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body '{"question":"Explain JWT"}'
```

### 4.3. Rate limiting

File:

- `04-api-gateway/production/rate_limiter.py`

Tra loi:

- Algorithm: `Sliding Window Counter`
- User limit: `10 req / 60s`
- Admin limit: `100 req / 60s`
- Admin duoc "bypass" mot phan bang cach dung `rate_limiter_admin` thay vi `rate_limiter_user`

Test:

```powershell
for ($i = 1; $i -le 20; $i++) {
  try {
    Invoke-RestMethod `
      -Uri "http://localhost:8000/ask" `
      -Method Post `
      -Headers @{ Authorization = "Bearer $token" } `
      -ContentType "application/json" `
      -Body ("{`"question`":`"Test $i`"}")
  } catch {
    $_.Exception.Message
    break
  }
}
```

Ket qua dung la se gap `429 Too Many Requests`.

### 4.4. Cost guard

File:

- `04-api-gateway/production/cost_guard.py`

Repo hien tai implement:

- Per-user budget: `$1/day`
- Global budget: `$10/day`
- Warning threshold: `80%`
- Storage: in-memory

Luu y: phan `CODE_LAB.md` co pseudo-code noi den Redis va `$10/thang`, nhung code dang co trong repo nay thuc te la in-memory theo ngay.

### 4.5. Checkpoint 4

- API key auth: co
- JWT auth: co
- Rate limit: co
- Cost guard: co

Ghi chu repo:

- Minh da sua middleware security trong `04-api-gateway/production/app.py` de vi du chay duoc on dinh.

## 5. Scaling va Reliability

### 5.1. Ban develop: health va readiness

File:

- `05-scaling-reliability/develop/app.py`

Cac endpoint:

- `/health`: liveness probe
- `/ready`: readiness probe

Test:

```powershell
cd .\05-scaling-reliability\develop
python app.py
```

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:8000/ready"
Invoke-RestMethod `
  -Uri "http://localhost:8000/ask?question=Long%20task" `
  -Method Post
```

Ghi chu:

- Tren may minh, `/health` tra `degraded` vi memory check vuot nguong.
- `/ready` van `True`.

### 5.2. Graceful shutdown

Code da co:

- `lifespan()` tat readiness khi shutdown
- Cho request dang xu ly xong toi da 30 giay
- Bat `SIGTERM` va `SIGINT`
- `uvicorn.run(... timeout_graceful_shutdown=30)`

Y nghia:

1. Khong nhan request moi
2. Cho request dang chay xong
3. Moi tat process

### 5.3. Stateless design

Anti-pattern:

```python
conversation_history = {}
```

Thiet ke dung:

- Khong luu session trong RAM cua tung instance
- Luu session/history ra storage chung, o day la Redis

Trong repo:

- `save_session()`
- `load_session()`
- `append_to_history()`

Neu co Redis -> dung Redis  
Neu khong co Redis -> fallback in-memory de demo

### 5.4. Ban production: local verification

File:

- `05-scaling-reliability/production/app.py`

Test local khong can Redis:

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Request 1:

```powershell
$r1 = Invoke-RestMethod `
  -Uri "http://localhost:8000/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"question":"What is Docker?"}'
```

Request 2 cung session:

```powershell
$sid = $r1.session_id
Invoke-RestMethod `
  -Uri "http://localhost:8000/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body ("{`"question`":`"Why do we need containers?`",`"session_id`":`"$sid`"}")
```

Xem history:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/chat/$sid/history"
```

### 5.5. Load balancing va multi-instance

File:

- `05-scaling-reliability/production/docker-compose.yml`
- `05-scaling-reliability/production/nginx.conf`
- `05-scaling-reliability/production/test_stateless.py`

Kien truc:

- `agent`
- `redis`
- `nginx`

Lenh:

```powershell
docker compose -f .\05-scaling-reliability\production\docker-compose.yml up --scale agent=3
```

Test:

```powershell
python .\05-scaling-reliability\production\test_stateless.py
```

Ket qua mong doi:

- `served_by` thay doi giua cac instance
- session history van con vi state o Redis

Ghi chu repo:

- Minh da sua compose build path
- Minh da them `Dockerfile` va `requirements.txt` cho `05-scaling-reliability/production`
- Minh da bo `env_file` khong ton tai
- Tren may nay chua verify full compose vi co the gap Docker Hub pull rate limit khi keo `redis`/`nginx`

### 5.6. Checkpoint 5

- Health check: co
- Readiness check: co
- Graceful shutdown: co
- Stateless session model: co
- Load balancing qua Nginx: co trong compose + nginx config

## Tong ket nhanh

Neu hoc de hieu ban chat:

1. Part 1 day cach chuyen tu code chi chay local sang code hop production.
2. Part 2 day cach dong goi moi truong bang Docker.
3. Part 3 day cach dua service len cloud.
4. Part 4 day cach bao ve API bang auth, rate limit, cost guard.
5. Part 5 day cach lam service ben hon, scale duoc, va khong mat session khi chay nhieu instance.

## Ghi chu thuc te khi lam tren may Windows/PowerShell

- Nhieu endpoint trong ban `develop` nhan `question` qua query string, khong nhan JSON body.
- Trong PowerShell, uu tien:

```powershell
Invoke-RestMethod
```

thay vi copy nguyen lenh `curl` kieu bash.

- Khi chay Docker, neu gap loi keo image:

`You have reached your unauthenticated pull rate limit`

thi do la gioi han Docker Hub, khong phai loi code.
