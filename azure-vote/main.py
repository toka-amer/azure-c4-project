import logging
import os
import socket
import redis
from flask import Flask, render_template, request

# App Insights
from opencensus.ext.azure.log_exporter import AzureEventHandler, AzureLogHandler

# -------------------------------
# CONFIGURE APP INSIGHTS LOGGERS
# -------------------------------
INSTRUMENTATION_KEY = "2b2cb4e4-f81d-4d2c-b5b7-3e6a8644bc16"

# General logs
logger = logging.getLogger("app_logger")
logger.setLevel(logging.INFO)
logger.addHandler(AzureLogHandler(connection_string=f"InstrumentationKey={INSTRUMENTATION_KEY}"))

# Events logger (for App Insights Events blade)
event_logger = logging.getLogger("event_logger")
event_logger.setLevel(logging.INFO)
event_logger.addHandler(AzureEventHandler(connection_string=f"InstrumentationKey={INSTRUMENTATION_KEY}"))

# -------------------------------
# FLASK APP
# -------------------------------
app = Flask(__name__)
app.config.from_pyfile("config_file.cfg")

# Voting buttons
button1 = os.getenv("VOTE1VALUE", app.config["VOTE1VALUE"])
button2 = os.getenv("VOTE2VALUE", app.config["VOTE2VALUE"])
title = os.getenv("TITLE", app.config["TITLE"])

# Redis
r = redis.Redis()

# Show host if needed
if app.config["SHOWHOST"] == "true":
    title = socket.gethostname()

# Initialize Redis counters
if not r.get(button1):
    r.set(button1, 0)
if not r.get(button2):
    r.set(button2, 0)

# -------------------------------
# ROUTES
# -------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        # Get current vote counts
        vote1 = r.get(button1).decode("utf-8")
        vote2 = r.get(button2).decode("utf-8")
        return render_template(
            "index.html",
            value1=int(vote1),
            value2=int(vote2),
            button1=button1,
            button2=button2,
            title=title,
        )

    elif request.method == "POST":
        vote = request.form["vote"]

        if vote == "reset":
            # Reset Redis
            r.set(button1, 0)
            r.set(button2, 0)
            vote1 = r.get(button1).decode("utf-8")
            vote2 = r.get(button2).decode("utf-8")

            # Log reset as custom events
            event_logger.info("Cats Vote Reset", extra={"custom_dimensions": {"vote": vote1}})
            event_logger.info("Dogs Vote Reset", extra={"custom_dimensions": {"vote": vote2}})

        else:
            # Increment vote in Redis
            r.incr(vote, 1)
            vote1 = r.get(button1).decode("utf-8")
            vote2 = r.get(button2).decode("utf-8")

            # Log votes as custom events
            if vote == button1:
                event_logger.info("Cats Vote", extra={"custom_dimensions": {"vote": vote1}})
            elif vote == button2:
                event_logger.info("Dogs Vote", extra={"custom_dimensions": {"vote": vote2}})

        # Return updated page
        return render_template(
            "index.html",
            value1=int(vote1),
            value2=int(vote2),
            button1=button1,
            button2=button2,
            title=title,
        )

# -------------------------------
# START APP
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", threaded=True, debug=True)
