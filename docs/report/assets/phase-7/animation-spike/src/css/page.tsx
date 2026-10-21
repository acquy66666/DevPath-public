import { CELEBRATE, REST } from "../_gen/naomi";
import { NaomiFrame } from "../_parts/naomi-frame";
import { Stage } from "../_parts/stage";
import "../_gen/keyframes.css";

// CSS keyframes generated from choreography.json; no JavaScript of its own.
export default function Page() {
  return (
    <Stage variant="css">
      <NaomiFrame celebrate={CELEBRATE} rest={REST} playing />
    </Stage>
  );
}
