# Publication Checklist

Complete these steps in order when publishing or correcting a release.

1. Decide whether any patent filing is desired before public disclosure.
2. Preserve every existing tag. Never move or rewrite a published release.
3. Rerun both deterministic artifacts from their pinned environments and
   compare their outputs byte-for-byte with the committed JSON.
4. Rebuild figures, manuscript, and evidence manifest.
5. Run the complete test suite and inspect the scoped Git diff.
6. Push `main` and a new annotated version tag.
7. Create a GitHub release from that tag and attach `paper/paper.pdf` plus the
   primary JSON evidence.
8. Enable Zenodo for the repository and archive the GitHub release.
9. Add the resulting DOI to `CITATION.cff` and the README in a later release.
10. Submit the exact tagged manuscript to an appropriate preprint or workshop.

The local Git commit and tag establish a precise artifact identity. A GitHub
release adds a public timestamp. A DOI archive adds an independent,
version-specific scholarly record.
