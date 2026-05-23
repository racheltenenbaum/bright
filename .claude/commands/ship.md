Stage all changes, commit, push, rebuild the frontend, sync to iOS, and restart the dev server.

Steps:
1. Run `git status` to show what's being committed.
2. If the working tree is already clean, skip to step 6.
3. Run `git diff --stat HEAD` and `git diff HEAD` to understand the changes. Suggest a commit message and wait for the user to confirm or edit it before doing anything else.
4. Run `git add -A` to stage everything.
5. Run `git commit -m "<confirmed message>"`.
6. Run `git push`.
7. Run `cd /Users/racheltenenbaum/projects/bright/client && npm run build && npx cap sync ios`.
8. Kill any running Vite dev server with `pkill -9 -f vite` (ignore errors if none running), then run `npm --prefix /Users/racheltenenbaum/projects/bright/client run dev` in the background.
9. Tell the user "Done!"
