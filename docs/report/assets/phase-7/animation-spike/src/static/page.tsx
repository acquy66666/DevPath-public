import { CELEBRATE, REST } from "../_gen/naomi";
import { NaomiFrame } from "../_parts/naomi-frame";
import { Stage } from "../_parts/stage";

// Baseline: the same drawing and shell, nothing animated.
export default function Page() {
  return (
    <Stage variant="static">
      <NaomiFrame celebrate={CELEBRATE} rest={REST} playing={false} />
    </Stage>
  );
}
