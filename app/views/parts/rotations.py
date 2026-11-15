"""Section 3: rotation options. One headline, the things to know, three strategy cards and the evidence for each."""
import streamlit as st

from core import engine
from core.styles import html
from views.parts.ui import bullets, head, strategy_card


def render(r, strategies, current, alts, best):
    head("repeat", "Rotation options", "Your current rotation next to the best feasible alternatives for your priorities and farm situation. Change the setup above and the suggestions change.")
    if best is None:
        st.warning("No alternative rotation passes the feasibility checks for your situation. See the notes below.")
    elif best.get("near_tie"):
        st.markdown(f"**Close call:** {best['name']} and {alts[1]['name']} score almost the same for your priorities. Choose on the trade-offs, not the order.")
    else:
        lead = "Your current rotation scores best for these priorities. **Best alternative:**" if current["rank"] == 1 else "**Top suggestion for your priorities:**"
        st.markdown(f"{lead} {best['name']}: bare soil **{current['bare_months_per_year']:.1f}** to **{best['bare_months_per_year']:.1f}** months a year.")
    with st.container(border=True, key="things_to_know"):
        st.markdown("**Things to know**")
        for n in r["notices"]:
            (st.caption if n.startswith("Near-tie") and best is not None and best.get("near_tie") else st.info)(n)
        sn = engine.sensitivity_note(r["priorities"])
        if sn and sn[1] < 0.6:
            st.warning(f"Sensitive result. For farmers who put {sn[0].replace(' first', '')} first, the suggested pair stayed the same in only {100 * sn[1]:.0f}% of {sn[2]} runs "
                       "with uncertain crop parameters varied. Treat the order of the suggestions as uncertain.")
        with st.expander("Known limitations of this version"):
            bullets(r["known_limitations"])
    cols = st.columns(3, gap="medium")
    for col, strat in zip(cols, strategies):
        with col:
            strategy_card(strat, r)
    if len(alts) < 2:
        st.info(f"Only {len(alts)} alternative(s) can be shown for your situation.")
    st.markdown("**Why each option? Evidence, feasibility, benefits, gaps and risks**")
    for strat in strategies:
        with st.expander(f"{strat['name']}: {100 * strat['scores']['total']:.0f}/100, {engine.FEASIBILITY[strat['feasibility']['status']]}"):
            st.markdown(f"**Why suggested:** {strat['why']}")
            if strat.get("near_tie_with"):
                st.markdown("**Close call with:** " + ", ".join(engine.CANDIDATES[k]["name"] for k in strat["near_tie_with"]) + f" (difference below {engine.NEAR_TIE:.2f}; a display rule, not a statistical test).")
            st.markdown("**Feasibility checks**")
            bullets([f"{engine.FEASIBILITY.get(i['severity'], 'Note')}: {i['message']}" for i in strat["feasibility"]["issues"]] or ["No known blocking constraint."])
            st.markdown("**Evidence from the data**"); bullets(strat["evidence"])
            if strat["benefits"]:
                st.markdown("**Benefits**"); bullets(strat["benefits"])
            st.markdown("**Information gaps**"); bullets(strat["information_gaps"])
            st.markdown("**Check with a local expert before deciding**"); bullets(strat["risks_for_local_review"])
