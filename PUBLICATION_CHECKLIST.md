# Publication Checklist

Complete these steps in order when making the local release public.

1. Decide whether any patent filing is desired before public disclosure.
2. Create the public GitHub repository without rewriting the local release
   commit.
3. Push `main` and the annotated `v0.1.0` tag.
4. Create a GitHub release from `v0.1.0` and attach `paper/paper.pdf`.
5. Enable Zenodo for the repository and archive the GitHub release.
6. Add the resulting DOI to `CITATION.cff` and the README in a later commit.
7. Submit the exact tagged manuscript to an appropriate preprint or workshop.
8. Preserve the original tag. Corrections should use a new version.

The local Git commit and tag establish a precise artifact identity. A GitHub
release adds a public timestamp. A DOI archive adds an independent,
version-specific scholarly record.
