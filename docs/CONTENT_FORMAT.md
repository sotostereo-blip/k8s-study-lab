# Content format

All study content lives in `content/` as YAML, separate from the code, so anyone
can add or fix questions with a pull request.

```
content/
├── glossary.yaml               # shared technical glossary
└── kcna/
    ├── exam.yaml               # exam metadata and domains with weights
    └── <domain-id>.yaml        # one file per domain
```

## Question

```yaml
domain: kubernetes-fundamentals     # must match a domain id in exam.yaml
questions:
  - id: kcna-fund-001               # unique: <exam>-<domain short>-<number>
    difficulty: 1                   # 1 = basic, 2 = intermediate, 3 = advanced
    type: single                    # single | multiple
    question: What is the smallest deployable unit ...?
    options:                        # 2 to 6 options, ids a..f
      - { id: a, text: "A container" }   # always quote: commas break flow style
      - { id: b, text: "A Pod" }
    answer: [b]                     # list; exactly 1 id for single, 2+ for multiple
    explanation: |                  # why the answer is right (and others wrong)
      ...
    docs:                           # at least one link to official docs
      - https://kubernetes.io/docs/...
    glossary: [pod, container]      # ids from glossary.yaml (optional)
```

## Rules for contributors

1. **Original questions only.** Never publish questions remembered from the real
   exam. CNCF exams are covered by a confidentiality agreement. Write questions
   from the public curriculum and documentation.
2. Write in clear, simple English. The project is also for practising English.
3. Every question needs an explanation and at least one official docs link.
4. Keep options similar in length and make wrong options plausible (real
   concepts used in the wrong place). The validator warns when the right answer
   is much longer than every distractor.
5. Run `python scripts/validate_content.py` before opening a pull request.
