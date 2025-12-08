from flask import Flask, request, render_template
import os
import redis
import socket
import logging
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

# ==============================
#  CONFIGURE APP INSIGHTS
# ==============================

INSTRUMENTATION_KEY = "2b2cb4e4-f81d-4d2c-b5b7-3e6a8644bc16"

# ---- Logging ----
logger_provider = LoggerProvider(resource=Resource.create({SERVICE_NAME: "flask-vote-app"}))
handler = LoggingHandler(logger_provider=logger_provider)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# ---- Tracing ----
trace_provider = TracerProvider(
    resource=Resource.create({SERVICE_NAME: "flask-vote-app"})
)
span_processor = BatchSpanProcessor(
    OTLPSpanExporter(
        endpoint="https://dc.services.visualstudio.com/v2/track",
        headers={"x-api-key": INSTRUMENTATION_KEY},
    )
)
trace_provider.add_span_processor(span_processor)
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer(__name__)

# ==============================
#       FLASK APP
# ==============================

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

# Load configs
app.config.from_pyfile("config_file.cfg")

button1 = os.getenv("VOTE1VALUE", app.config["VOTE1VALUE"])
button2 = os.getenv("VOTE2VALUE", app.config["VOTE2VALUE"])
title = os.getenv("TITLE", app.config["TITLE"])

# Redis
r = redis.Redis()

# Change title to host if needed
if app.config.get("SHOWHOST") == "true":
    title = socket.gethostname()

# Initialize redis values
if not r.get(button1):
    r.set(button1, 0)
if not r.get(button2):
    r.set(button2, 0)

# ==============================
#       ROUTES
# ==============================

@app.route("/", methods=["GET", "POST"])
def index():
    # TEST SPAN for App Insights
    with tracer.start_as_current_span("test-span"):
        logger.info("Test span sent to App Insights", extra={"custom_dimensions": {"event": "test"}})

    if request.method == "GET":
        vote1 = r.get(button1).decode("utf-8")
        vote2 = r.get(button2).decode("utf-8")
        with tracer.start_as_current_span("GET votes"):
            pass
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

        vote = request.form["vote"]
        r.incr(vote, 1)
        vote1 = r.get(button1).decode("utf-8")
        vote2 = r.get(button2).decode("utf-8")
        logger.info("Vote submitted", extra={"custom_dimensions": {"vote": vote}})
        with tracer.start_as_current_span("POST vote"):
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
#       START APP
# ==============================

if __name__ == "__main__":
    # Run Flask app on all interfaces
    app.run(host="0.0.0.0", threaded=True, debug=True)
