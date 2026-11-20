# Instagram batch I

`captions-I.md` has every caption (Hindi, Hinglish version, alt text, hashtags), the calendar, and what must be true before the launch post.
`remotion-src/reels7.tsx` (four reels) and `remotion-src/posts.tsx` (five posts) are the sources. They sit on the shared components of the Remotion project (`ui.tsx`, `fonts.ts`, `reels5.tsx`) kept outside this repo; to rebuild, copy them into that project's `src/`, register them in `Root.tsx` and run `npx remotion render`/`still`.
The finished videos and images are delivered as files, not stored here.
