from .generic import FileListingFilter, LintBuildFilter, LogOutputFilter, SearchOutputFilter
from .git import GitDiffFilter, GitLogFilter, GitStatusFilter
from .tests import TestOutputFilter

FILTERS = (
    TestOutputFilter(),
    GitDiffFilter(),
    GitLogFilter(),
    GitStatusFilter(),
    LintBuildFilter(),
    SearchOutputFilter(),
    FileListingFilter(),
    LogOutputFilter(),
)
