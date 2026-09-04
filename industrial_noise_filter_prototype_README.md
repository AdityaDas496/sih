# Industrial Thermal-Noise Filter — Prototype

## Objective
Reduce routine industrial thermal detections before downstream fire classification.

## Inputs
- NASA FIRMS VIIRS Suomi-NPP 2025 archive
- GEM steel plant-level data
- GEM cement/concrete plant-level data
- GEM Global Coal Plant Tracker

## Current association rule
A FIRMS detection is considered an industrial-side candidate when its nearest known facility is <= 1 km away.

## Candidate population
- 646,376 total VIIRS detections
- 32,031 detections within 1 km of an industrial facility
- 1,118 industrial facilities in the India reference table
- 403 facilities had at least one <=1 km detection

## Prototype methodology
1. Build facility-specific thermal history.
2. Use Jan–Sep 2025 as a historical baseline.
3. Describe daily event count, total FRP, maximum FRP and spatial spread.
4. Compute robust facility-relative anomaly measures.
5. Use Isolation Forest as a secondary unsupervised anomaly signal.
6. Suppress only events that have a sufficiently established facility baseline and no strong anomaly evidence.
7. Forward the remaining candidates to Person 2.

## Important limitation
The prototype does NOT claim that suppressed detections are confirmed false alarms. Ground-truth fire/no-fire labels are still required for quantitative validation.

## Q4 forward-in-time demonstration
- 11,822 Q4 industrial-side events
- 9,944 suppressed
- 1,878 passed to Person 2
- 15.89% passed through

This is a prototype throughput result, not an accuracy result.
