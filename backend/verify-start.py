from run import app

settings = app.config["SETTINGS"]
app.run(host="127.0.0.1", port=settings.port, threaded=True)
