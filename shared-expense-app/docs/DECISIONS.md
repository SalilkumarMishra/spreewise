# DECISIONS

## Group and Membership Lifecycle Decisions (Priority 2)

### 1. Group Archiving vs Hard Deletion
- **Decision**: Deleting a group through the API performs a soft delete (marking `is_archived = True`) instead of a physical SQL `DELETE`.
- **Rationale**: Financial and expense histories must remain completely auditable for all group members, even if the group is no longer active. Deleting the group database records would break database cascades, leading to dangling/orphaned expenses or loss of historical ledger data.

### 2. Historical Membership Preservation (Soft-Departure)
- **Decision**: Memberships are never hard deleted. Leaving a group changes the membership status to inactive (`is_active = False`) and records the exact date of departure in the `left_at` field.
- **Rationale**: The core balance engine, CSV import parser, and expense distribution rules depend on membership state relative to dates (e.g. Meera leaves on March 31, Sam joins on April 15). Removing these records entirely would corrupt the history of who was active in the group when past expenses were logged.

### 3. Support for Multiple Lifetimes (Leave/Rejoin History)
- **Decision**: Users are allowed to leave and rejoin the same group multiple times. This is implemented by maintaining a list of discrete membership records in the database, with a partial unique constraint allowing at most one *active* membership record per user per group at any given time.
- **Rationale**: Enables auditability of non-contiguous memberships. A user can leave for a vacation or period, and rejoin later, creating two separate records to denote distinct active windows.
