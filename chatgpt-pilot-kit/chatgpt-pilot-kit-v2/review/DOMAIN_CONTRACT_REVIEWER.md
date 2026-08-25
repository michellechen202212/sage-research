# Synthetic Commerce Investigation Domain Contract — V2

1. Source identity is not replaced by a display/reference value.
2. Every independently consumable serving projection, collection, or row/fact type has one unambiguous grain.
3. Independent child collections remain independent unless an explicit bridge relates them.
4. Parent-level amounts do not become additive when repeated on child rows.
5. Payment, authorization, and settlement are distinct facts.
6. POS item occurrences and tender legs are distinct facts.
7. Event timestamps retain their event meaning.
8. Serving projections may simplify, but grain must be unambiguous and information loss must be explicit.
9. Derived signals are not source facts.
10. Unknown identity/cardinality remains UNKNOWN.

Canonical invariants:
I01 order_id is order identity; order_number is a reference.
I02 order_line_id is line identity; (order_id, sku) is not.
I03 same-SKU distinct lines remain distinct.
I04 lines and payments are independent order children.
I05 no invented line/payment allocation.
I06 authorization attempts remain separate and are not summed as amount paid.
I07 settlement events remain distinct from authorization.
I08 POS items and tenders are independent receipt children.
I09 no invented item/tender allocation.
I10 receipt_total is non-additive across receipt children.
I11 ordered_total is non-additive across order children.
I12 repeated same-SKU POS occurrences remain distinct.
I13 tender_type is classification, not tender identity.
I14 every monetary output identifies its event/grain semantic.
I15 every exposed timestamp retains source event meaning.
I16 every independently consumable serving projection, collection, or row/fact type has exactly one unambiguous grain, established either by projection/schema documentation or by stable identity and structure without contradictory cardinality.
I17 derived facts remain explicitly derived.
I18 visible amounts have source-ID and aggregation lineage.
I19 unknown identities/relationships are not invented.
I20 unified stories compose typed facts or bounded collections, not unrestricted cross-products.

Application note: these invariants also apply to compact projections, exports, summaries, and timeline outputs.
## Meaning of "serving object"

A serving object is an independently consumable projection, a collection exposed by that projection, or a row/fact type that a consumer can interpret or iterate independently. A projection-level or schema-level grain declaration may govern homogeneous rows. Each heterogeneous collection must have its own unambiguous grain.

A nested attribute or value wrapper is not a separate serving fact merely because it is serialized as an object. Nested amount, timestamp, and lineage wrappers inherit the grain of their containing fact unless they form independently iterable collections or independently identified facts. Stable identity, structure, and cardinality may establish grain without a literal `grain` property. Semantic ambiguity, mixed grain, contradictory identity/cardinality, or unsupported multiplicity violates the contract; metadata brevity alone does not.
