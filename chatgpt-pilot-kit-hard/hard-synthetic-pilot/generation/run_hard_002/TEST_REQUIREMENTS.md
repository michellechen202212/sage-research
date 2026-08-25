# Ordinary Testing Requirements

The implementation must include automated tests that:

- load the supplied SQLite schema and fixtures in a clean database;
- exercise successful and missing entity-detail lookups;
- verify all required sections occur in the customer investigation response;
- verify the timeline is chronological and each entry has a type and timestamp;
- exercise every documented compact-projection filter;
- verify deterministic output ordering;
- reconcile source row counts and monetary values returned by the interfaces to the fixture database;
- run from one documented command and require no network service.

