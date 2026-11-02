# Change request: catch an accept BEFORE it lapses

**Repo:** this repository. **Area:** whatever the repository already uses to catch expired security-scanner accepts
(the accept lists for osv-scanner and trivy).

**Background.** CI now catches an accept that has already expired. By then the finding is already back. We want a
warning window instead.

**Required behaviour.**
1. CI must also FAIL when any accept will expire within the next 14 days, naming the entry and its date, so it is
   re-reviewed before it lapses.
2. An accept expiring more than 14 days from today must not fail CI.
3. Everything caught before (an already-expired accept, in every accept file) is still caught, and the clean repository
   still passes.

**Acceptance criteria.**
- [ ] An accept that expires in 7 days, in any of the accept files, makes CI fail.
- [ ] An accept that expires in 60 days does not.
- [ ] Already-expired accepts are still caught, and the unmodified repository passes.

**Tools available on PATH:** `bats`, `python3` (with PyYAML), `promtool`.
