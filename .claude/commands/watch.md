Add, remove, or list tickers in the `claude.watch` moomoo watchlist.

**Usage examples:**
- `/watch MSFT` — add MSFT to claude.watch
- `/watch add MSFT ASML` — add multiple tickers
- `/watch remove MSFT` — remove a ticker
- `/watch list` — show current watchlist

Run the appropriate command based on the arguments provided:

```
/Users/mandl/Desktop/projects/openscan/venv/bin/python3 /Users/mandl/Desktop/projects/openscan/watch.py $ARGUMENTS
```

Display the output to the user. If no arguments are given, default to `list`.
