from . import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=app.config.get("PORT", 8080), threaded=True)
