# Regenerating the plan

    pip install pyyaml
    python _source/render.py .

The renderer validates dependencies, epic/story consistency and cycles, and computes build waves, Blocks links and the critical path.
