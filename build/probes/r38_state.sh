cd /Users/bharris/Programs/CodeMonkey
echo "== reachability (importers of each orphan module) =="
for m in graphquery certify branches bestofn rubrics adaptivemem learnedctx; do
  hits=$(grep -rl "$m" src/codemonkey --include='*.py' | grep -v "/$m.py" | tr '\n' ' ')
  echo "$m: ${hits:-NO-IMPORTER}"
done
echo
echo "== tools.SPECS =="
uv run python -c "from codemonkey import tools; print(sorted(tools.SPECS))"
echo
echo "== module files =="
ls src/codemonkey/*.py
