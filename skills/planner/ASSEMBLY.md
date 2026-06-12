THIS REQUEST IS AN ASSEMBLY of physically DISTINCT bodies. Emit an ASSEMBLY IR
(NOT a single part):
{
  "version":"1.0","units":"mm","process":"<...>","kind":"assembly",
  "components":[ {"id":"<role>","grounded":true|false,"design":<a full Part IR>} ],
  "mates":[ {"type":"stack_on|concentric|coincident_face|custom","a":"<id>","b":"<id>","params":{...}} ]
}
Rules:
- Each component.design is a normal Part IR (the SAME schema you use for parts,
  with its own features + asserts). Build each component in its OWN local frame
  (base-centered at origin, +Z up).
- Exactly ONE component is "grounded": true. Every other component must be joined
  by a mate, forming a connected tree (no floating parts, no cycles).
- DECLARE mate INTENT — do NOT compute transforms. The compiler solves placement:
    stack_on  : b sits on a's top face, centered.
    concentric: b's axis aligns to a's (e.g. shaft in bore); params {z_offset, bore_mm, shaft_mm, fit}.
    coincident_face: like stack_on with params {gap}.
    custom    : params {translate:[x,y,z]} (last resort).
- Components must NOT interfere (overlap) unless an interference fit is declared,
  and each must actually touch its mate partner.
Output the final ASSEMBLY IR as ONE ```json block.