# piazza-attendant
Provides notifications of questions that go unanswered on piazza after a certain threshold of time, as well as a summary of all unanswered questions.

## usage
Assuming python (>=3.12) and pip are installed:
```sh
pipx install poetry # if poetry is not installed
poetry install
```

Then copy `example-config.toml` and adjust the configuration values accordingly, and run the following command to start the service:

```sh
poetry run python main.py my-config.toml
```