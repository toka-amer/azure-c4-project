from flask import Flask, request, render_template
import os
import redis
import socket
import logging

# OpenCensus imports
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from opencensus.ext.flask.flask_middleware import FlaskMiddleware

# ==============================
# CONFIGURE APP INSIGHTS
# ==============================

INSTRUMENTATION_KEY = "2b2cb4e4-f81d-4d2c-b5b7-3e6a8644bc16"

# ---- Logging ----
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}'))
logger.setLevel(logging.INFO)

# ---- Tracing ----
tracer = Tracer(
    exporter=AzureExporter(connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}'),
    sampler=ProbabilitySampler(1.0),
)

# ==============================
# FLASK APP
# ==============================

app = Flask(__name__)

# Middleware to automatically trace requests
FlaskMiddleware(
    app,
    exporter=AzureExporter(connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}'),
    sampler=ProbabilitySampler(1.0)
)

# Load configs
app.config.from_pyfile("config_file.cfg")

button1 = os.getenv("VOTE1VALUE", app.config["VOTE1VALUE"])
button2 = os.getenv("VOTE2VALUE", app.config["VOTE2VALUE"])
title = os.getenv("TITLE", app.config["TITLE"])

# Redis
r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"))

# Change title to host if needed
if app.config.get("SHOWHOST", "false").lower() == "true":
    title = socket.gethostname()

# Initialize redis values
if not r.get(button1):
    r.set(button1, 0)
if not r.get(button2):
    r.set(button2, 0)

# ==============================
# ROUTES
# ==============================

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        vote1 = r.get(button1).decode("utf-8")
        vote2 = r.get(button2).decode("utf-8")

        # Log GET request
        logger.info("GET votes", extra={"custom_dimensions": {"vote1": vote1, "vote2": vote2}})

        return render_template(
            "index.html",
            value1=int(vote1),
            value2=int(vote2),
            button1=button1,
            button2=button2,
            title=title,
        )

    # POST
    if request.method == "POST":
        if request.form["vote"] == "reset":
            r.set(button1, 0)
            r.set(button2, 0)

            vote1 = r.get(button1).decode("utf-8")
            vote2 = r.get(button2).decode("utf-8")

            logger.info("Votes reset", extra={"custom_dimensions": {"vote1": vote1, "vote2": vote2}})

            return render_template(
                "index.html",
                value1=int(vote1),
                value2=int(vote2),
                button1=button1,
                button2=button2,
                title=title,
            )

        # Normal voting
        vote = request.form["vote"]
        r.incr(vote, 1)

        vote1 = r.get(button1).decode("utf-8")
        vote2 = r.get(button2).decode("utf-8")

        logger.info("Vote submitted", extra={"custom_dimensions": {"vote": vote}})

        # Trace POST vote
        with tracer.span(name="POST vote"):
            pass

        return render_template(
            "index.html",
            value1=int(vote1),
            value2=int(vote2),
            button1=button1,
            button2=button2,
            title=title,
        )

# ==============================
# START APP
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", threaded=True, debug=True)
