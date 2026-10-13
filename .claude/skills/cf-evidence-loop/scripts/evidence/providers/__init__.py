"""Providers, one per question family. Each returns Evidence records and nothing else."""

from . import clinvar, crossref, europepmc, openfda, preprints, pubmed, reporter, trials  # noqa: F401

ALL = {"crossref": crossref, "openfda": openfda, "preprints": preprints, "clinvar": clinvar, "reporter": reporter,
       "pubmed": pubmed, "trials": trials, "europepmc": europepmc}
