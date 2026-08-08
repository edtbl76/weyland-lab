"""B106 review-lane smoke test — THROWAWAY, safe to delete.

Exists only to give the adopted AI review tools (PR-Agent, Sourcery, DeepSource,
CodeScene, CodeRabbit, Greptile) something concrete to flag, so we can confirm the
review pipeline works end to end. Delete the branch after the review lands.
"""


def summarize(items, prefix, suffix, separator, uppercase):
    # smells on purpose: 5 args, nested conditionals, string concat in a loop
    output = ""
    for item in items:
        if item is not None:
            if uppercase:
                output = output + prefix + str(item).upper() + suffix + separator
            else:
                output = output + prefix + str(item) + suffix + separator
    return output


def divide(a, b):
    # smell on purpose: no zero-division guard
    return a / b
