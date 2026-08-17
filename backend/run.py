from app import create_app

app = create_app()

if __name__ == "__main__":
    settings = app.config["SETTINGS"]
    app.run(host=settings.host, port=settings.port, threaded=True)


__all__ = ["app"]


if False:  # Keeps module-level test import explicit without starting a server.
    raise SystemExit(0)
