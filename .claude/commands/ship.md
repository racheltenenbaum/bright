Stage all changes, commit, push, rebuild the frontend, sync to iOS, and restart the dev server.

Steps:
1. Run `git status` to show what's being committed.
2. If the working tree is already clean, skip to step 6.
3. If there are uncommitted changes and no commit message was provided in $ARGUMENTS, run `git diff --stat HEAD` and `git diff HEAD` to understand the changes, suggest a concise commit message, and ask the user to confirm or provide their own.
4. Run `git add -A` to stage everything.
5. Run `git commit -m "<message>"` using the commit message from $ARGUMENTS or from the user's response.
6. Run `git push`.
7. Run `cd /Users/racheltenenbaum/projects/bright/client && npm run build && npx cap sync ios`.
8. Kill any running Vite dev server with `pkill -f "vite"` (ignore errors if none running), then run `cd /Users/racheltenenbaum/projects/bright/client && npm run dev` in the background. Always use the full `cd ... && npm run dev` form — never bare `npm run dev`.
9. Tell the user "Done!"
