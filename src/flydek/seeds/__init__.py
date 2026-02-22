# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Seed data for example domains.

The seeds module is intended for development and demos only.
Production deployments should configure their own Service Catalog
through the admin API -- the banking example data can be omitted
entirely by not calling any seed functions and by excluding this
module from the deployment (it has no runtime dependencies).

To remove previously seeded data, use ``unseed_banking_catalog``
or the CLI command ``flydek-seed banking --remove``.
"""

from flydek.seeds.banking import seed_banking_catalog, unseed_banking_catalog

__all__ = ["seed_banking_catalog", "unseed_banking_catalog"]
