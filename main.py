import uvicorn
import web

if __name__ == "__main__":
    uvicorn.run(web.app, host='0.0.0.0', port=8001, access_log=True, workers=1,
                proxy_headers=False, server_header=False, date_header=False)