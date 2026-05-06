#!/usr/bin/env python3
"""Watch list manager — add/remove/list tickers in the claude.watch moomoo watchlist."""

import sys

from moomoo import OpenQuoteContext, ModifyUserSecurityOp, RET_OK

from scanner import _moomoo_code, OPEND_HOST, OPEND_PORT

WATCHLIST_GROUP = "claude.watch"


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        print(f"Usage:")
        print(f"  python watch.py add MSFT AAPL    — add tickers to {WATCHLIST_GROUP}")
        print(f"  python watch.py remove MSFT      — remove tickers from {WATCHLIST_GROUP}")
        print(f"  python watch.py list             — show current {WATCHLIST_GROUP} watchlist")
        sys.exit(0)

    cmd = args[0].lower()
    tickers = [t.upper().strip(",") for t in args[1:]]

    ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)

    if cmd == "list":
        ret, data = ctx.get_user_security(WATCHLIST_GROUP)
        if ret == RET_OK and not data.empty:
            print(f"\n  {WATCHLIST_GROUP} watchlist ({len(data)} stocks):")
            for _, row in data.iterrows():
                print(f"    {row['code'].replace('US.', ''):<8} {row.get('name', '')}")
        else:
            print(f"\n  {WATCHLIST_GROUP} watchlist is empty or not found.")

    elif cmd == "add":
        if not tickers:
            print("  Error: specify at least one ticker.")
            sys.exit(1)
        codes = [_moomoo_code(t) for t in tickers]
        ret, data = ctx.modify_user_security(WATCHLIST_GROUP, ModifyUserSecurityOp.ADD, codes)
        if ret == RET_OK:
            print(f"\n  Added to '{WATCHLIST_GROUP}': {', '.join(tickers)}")
        else:
            print(f"\n  Error: {data}")

    elif cmd == "remove":
        if not tickers:
            print("  Error: specify at least one ticker.")
            sys.exit(1)
        codes = [_moomoo_code(t) for t in tickers]
        ret, data = ctx.modify_user_security(WATCHLIST_GROUP, ModifyUserSecurityOp.DEL, codes)
        if ret == RET_OK:
            print(f"\n  Removed from '{WATCHLIST_GROUP}': {', '.join(tickers)}")
        else:
            print(f"\n  Error: {data}")

    else:
        # Default: treat as 'add' if tickers passed directly (e.g. watch.py MSFT)
        all_tickers = [args[0].upper()] + tickers
        codes = [_moomoo_code(t) for t in all_tickers]
        ret, data = ctx.modify_user_security(WATCHLIST_GROUP, ModifyUserSecurityOp.ADD, codes)
        if ret == RET_OK:
            print(f"\n  Added to '{WATCHLIST_GROUP}': {', '.join(all_tickers)}")
        else:
            print(f"\n  Error: {data}")

    ctx.close()


if __name__ == "__main__":
    main()
