"""Measure how well the extractor reads a tender, on a set a human labelled.

Every other number this project prints is produced by the same code that is
being judged. These two modules are the exception: the truth comes from a
person reading the buyer's sentence, stored next to the raw payload, and the
harness only compares. That is what turns "60% of tenders are machine
readable" from a claim in a document into a figure anybody can re-measure
after a parser change.
"""
