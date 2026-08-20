---
id: injection-attacks
tags: [principle, security, backend]
surfaces-at: [functional-design, code-generation]
related: [input-validation, api-security, defense-in-depth, prompt-injection-defense]
complexity: intermediate
---

# Injection Attacks

## What It Is
A class of security vulnerabilities where untrusted data is sent to an interpreter as part of a command or query, causing the interpreter to execute unintended instructions. Injection is consistently the top OWASP vulnerability category. The root cause is always the same: mixing untrusted data with code or query structure without proper separation. The fix is always the same: use parameterized interfaces that separate data from instructions.

## When to Apply
- Any code that constructs database queries, shell commands, HTML output, XML, LDAP queries, or OS commands using user-supplied data
- Code review for any string interpolation or concatenation involving external input

## Key Concepts
- **SQL Injection**: Malicious SQL embedded in user input alters a database query. `SELECT * FROM users WHERE name = '` + userInput + `'` — input of `' OR '1'='1` bypasses authentication. Fix: parameterized queries / prepared statements — never string-concatenate SQL. ORMs use parameterized queries by default
- **Command Injection**: User input passed to shell commands. `os.system("ping " + host)` — host of `google.com; rm -rf /` executes both. Fix: avoid shell execution with user input; use subprocess with argument lists (no shell=True); validate input strictly
- **Cross-Site Scripting (XSS)**: Malicious scripts injected into web pages viewed by other users. Stored XSS (saved to database, served to victims), reflected XSS (echoed in response), DOM XSS (client-side DOM manipulation). Fix: HTML-encode all user-controlled output; use Content Security Policy (CSP); use frameworks that auto-escape (React, Django templates)
- **LDAP Injection**: User input inserted into LDAP queries without escaping. Fix: LDAP encoding libraries; parameterized LDAP queries
- **XML Injection / XXE (XML External Entity)**: Malicious XML that exploits entity expansion — can read local files, perform SSRF. Fix: disable external entity processing in XML parsers
- **NoSQL Injection**: JSON objects from user input alter MongoDB queries. `{ username: userInput }` where input is `{ $gt: "" }` matches all users. Fix: schema validation; never pass raw user objects to query operators
- **Prompt Injection**: User input in LLM prompts that hijacks model behavior. See Prompt Injection Defense entry
- **Parameterized Queries are Non-Negotiable**: For SQL, parameterized queries (prepared statements) eliminate SQL injection completely. There is no valid reason to construct SQL by string concatenation. This applies to every database access library in every language
- **Output Encoding Context**: HTML encoding for HTML context, JavaScript encoding for JS context, URL encoding for URL context. Encoding for the wrong context doesn't prevent injection

## In Practice
Method codebases use ORM query builders (SQLAlchemy, Prisma) for all database access — raw SQL only via parameterized query interfaces, never string interpolation. Shell commands avoid `shell=True`. All HTML output uses framework auto-escaping. Code review checks for string concatenation near database or shell execution points.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Injection Attacks**: Parameterized queries eliminate SQL injection — there is no excuse for string-concatenated SQL in 2024. For shell commands, use argument lists instead of shell strings; avoid shell=True entirely when user input is involved. For HTML output, use frameworks that auto-escape by default and treat any manual HTML construction as a red flag. The pattern is always the same: separate data from instructions using parameterized interfaces. Input validation reduces attack surface but is not a substitute for parameterized queries. → `engineering-knowledge-repository/injection-attacks.md`

## Related Entries
- [Input Validation](input-validation.md) — input validation reduces injection attack surface but is not sufficient alone
- [API Security](api-security.md) — injection prevention is a core API security requirement
- [Defense in Depth](defense-in-depth.md) — injection prevention is one layer of a defense-in-depth security posture
- [Prompt Injection Defense](prompt-injection-defense.md) — injection attacks applied to LLM prompt contexts
