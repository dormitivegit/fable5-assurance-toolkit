# Module scope and non-goals

The product is limited to PM-01 through PM-06 and the public CLI documented in
the README. It is not an agent platform, workflow engine, policy learner,
daemon, permanent task database, cloud service, generic schema framework,
automatic project writer, deployment system, or promotion authority.

Each module is independently removable: deleting its registration, module,
dependent synthetic pilot adapter, tests, contracts, and fixtures requires no
user-data migration or persistent state cleanup. Pilot imports are lazy so an
unrelated removed module does not make the remaining pilot surface unloadable.
