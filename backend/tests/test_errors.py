from app.errors import Kind, internal, kind_of, not_found, public_message, validation


def test_opaque_error_wrapping():
    raw_exc = RuntimeError("sqlite: disk I/O failure or syntax error")
    err = internal("db.telemetry.insert")
    # Attach cause
    err.__cause__ = raw_exc

    assert kind_of(err) is Kind.INTERNAL
    assert err.op == "db.telemetry.insert"

    # Public message MUST be generic and never leak cause
    pub = public_message(err)
    assert pub == "Something went wrong."
    assert "disk I/O" not in pub

    # Random unexpected exception also gets generic message
    assert public_message(Exception("crash")) == "Something went wrong."


def test_validation_error_message():
    err = validation("api.telemetry.validate", "samples[0].spo2 must be between 50 and 100")
    assert kind_of(err) is Kind.VALIDATION
    assert err.public_message() == "validation failed: samples[0].spo2 must be between 50 and 100"


def test_not_found_error():
    err = not_found("db.astronaut.get", "Astronaut 'astro-x' not found.")
    assert kind_of(err) is Kind.NOT_FOUND
    assert err.public_message() == "Astronaut 'astro-x' not found."
