# bidscout — should you bid on this tender?

*A plain-language overview. The technical README is [here](README.md).*

## The problem

Romanian public bodies publish thousands of tenders a year. For a company
that sells to the state, every one of them means the same slow job: open a
file of 30 to 80 pages, find the conditions buried inside, and work out
whether the company even qualifies. That usually takes **two or three days per
tender**, and most of the time the answer turns out to be "no".

The tools on the market today tell you *that* a tender was published. None of
them tell you *whether you can win it*.

## What bidscout does

bidscout reads every new tender and compares it with your company, then
gives one clear answer:

| Answer | Meaning |
|---|---|
| **GO** | You meet every condition the buyer set. Worth preparing a bid. |
| **CHECK** | Something needs a human look: a condition was unclear, a figure was missing, or the tender is split into lots. |
| **NO-GO** | You fall short of a condition. For example, the buyer asks for a yearly turnover of 2.7 million lei and you have 1.2 million. |

Every answer comes with the **buyer's own sentence** it was based on. You never
have to take the tool's word for it: you can read the line and decide for
yourself.

It is careful by design. When it isn't sure, it says **CHECK**, never NO-GO,
so it will not talk you out of a tender you could have won.

Your company is described by a handful of numbers: yearly turnover, the size
of similar contracts you have delivered, how much cash you can put up as a
guarantee, and the kinds of work you do. Nothing else is needed.

## Where the data comes from

All of it comes from **SEAP / SICAP (e-licitatie.ro)**, the official Romanian
public procurement portal, where every public tender has to be published.

- The data is **public**: no login, no paid subscription, no scraping behind a
  password.
- bidscout reads the same information anyone can see on the portal, just
  automatically and every day.
- Nothing is invented. If a number is not in the buyer's own text, the tool
  does not guess it.

## Why it is useful

- **Time saved.** A first decision in minutes instead of days, so people spend
  their effort only on tenders worth bidding for.
- **Fewer missed opportunities.** Every new tender gets looked at, not only the
  ones someone had time to open.
- **Fewer wasted bids.** Tenders you cannot qualify for are flagged before
  anyone starts on the paperwork.
- **Trust.** Every verdict shows the exact sentence behind it, so a manager or
  a bid consultant can check it in seconds.

It is meant for **small and medium companies** that sell to the state, and for
the **bid consultants** who prepare tenders for them.

## Where it is today

- It works on **real tenders**. On its first live run it collected 129
  newly published tenders, read the full conditions of all 44 standard
  tenders, and gave each one a verdict.
- A public web page shows the results for an example company, with the
  reasons behind every verdict.
- It is still a working prototype. It runs when started by hand, and it does
  not yet read every type of tender (see below).

## Next steps

bidscout is developed as an open showcase project rather than a commercial
product. The next steps make it more accurate and easier to trust:

1. **Only suggest relevant tenders.** Today a tender from a different industry
   can still come out as a GO. Next, tenders outside the company's line of work
   are held back.
2. **Run every day on its own,** so the page always shows that day's tenders.
3. **Prove the accuracy.** Check its answers against 30 tenders reviewed by a
   person, and publish the result on the page.
4. **Use AI carefully** to read the conditions the rules cannot, with every
   figure still tied to the buyer's own sentence and checked before it counts.
5. **Cover the rest of the market.** About two thirds of tenders use a
   simplified format that bidscout cannot read yet.

## What it is not

bidscout is a **decision aid**. It does not give legal advice, and it never
submits anything on your behalf. You read the tender, you decide, and you
send the bid.
