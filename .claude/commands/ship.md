Stage all changes, commit, push, rebuild the frontend, sync to iOS, and start the dev server.

Steps:
1. Run `git status` to show what's being committed.
2. If the working tree is already clean, skip to step 6.
3. If there are uncommitted changes and no commit message was provided in $ARGUMENTS, ask the user for a commit message before proceeding.
4. Run `git add -A` to stage everything.
5. Run `git commit -m "<message>"` using the commit message from $ARGUMENTS or from the user's response.
6. Run `git push`.
7. Run `cd client && npm run build && npx cap sync ios`.
8. Run `cd client && npm run dev`.
9. Tell the user Railway will rebuild and restart both services (usually 1–3 minutes).
