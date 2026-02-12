curl -X POST http://localhost:9001/bootstrap

curl http://localhost:9001/orders/1002 | python3 -m json.tool
curl http://localhost:9001/kpis/1002 | python3 -m json.tool
curl -X POST http://localhost:9001/detect-deviation/1002 | python3 -m json.tool
curl -X POST http://localhost:9001/trigger-agent/1002 | python3 -m json.tool
curl http://localhost:9001/view-response/1002 | python3 -m json.tool