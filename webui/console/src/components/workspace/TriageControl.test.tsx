import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TriageControl } from "@/components/workspace/TriageControl";

describe("TriageControl", () => {
  it("submits a status that needs no justification straight away", async () => {
    const onChange = vi.fn();
    render(<TriageControl status="open" onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText("Finding review status"), "triaged");

    expect(onChange).toHaveBeenCalledWith({ status: "triaged" });
  });

  it("asks for a reason before accepting a risk, and does not submit without one", async () => {
    const onChange = vi.fn();
    render(<TriageControl status="open" onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText("Finding review status"), "accepted_risk");

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Reason")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record" })).toBeDisabled();
  });

  it("sends the justification under the field name the backend requires", async () => {
    const onChange = vi.fn();
    render(<TriageControl status="open" onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText("Finding review status"), "accepted_risk");
    await userEvent.type(screen.getByLabelText("Reason"), "  compensating control in place  ");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));

    expect(onChange).toHaveBeenCalledWith({
      status: "accepted_risk",
      accepted_risk_reason: "compensating control in place",
    });
  });

  it("uses the false-positive field for a false positive", async () => {
    const onChange = vi.fn();
    render(<TriageControl status="open" onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText("Finding review status"), "false_positive");
    await userEvent.type(screen.getByLabelText("Reason"), "not reachable");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));

    expect(onChange).toHaveBeenCalledWith({ status: "false_positive", false_positive_reason: "not reachable" });
  });

  it("refuses whitespace as a justification", async () => {
    const onChange = vi.fn();
    render(<TriageControl status="open" onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText("Finding review status"), "accepted_risk");
    await userEvent.type(screen.getByLabelText("Reason"), "   ");

    expect(screen.getByRole("button", { name: "Record" })).toBeDisabled();
    await userEvent.keyboard("{Enter}");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("cancelling leaves the finding's status untouched", async () => {
    const onChange = vi.fn();
    render(<TriageControl status="open" onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText("Finding review status"), "accepted_risk");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Finding review status")).toHaveValue("open");
  });

  it("re-selecting the current status does nothing", async () => {
    const onChange = vi.fn();
    render(<TriageControl status="triaged" onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText("Finding review status"), "triaged");

    expect(onChange).not.toHaveBeenCalled();
  });

  it("is disabled while a mutation is in flight", () => {
    render(<TriageControl status="open" busy onChange={vi.fn()} />);
    expect(screen.getByLabelText("Finding review status")).toBeDisabled();
  });
});
