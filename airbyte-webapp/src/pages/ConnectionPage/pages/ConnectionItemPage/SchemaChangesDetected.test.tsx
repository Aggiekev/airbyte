import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockConnection, TestWrapper } from "test-utils/testutils";

import { SchemaChange } from "core/request/AirbyteClient";
import en from "locales/en.json";

// eslint-disable-next-line css-modules/no-unused-class
import styles from "./SchemaChangesDetected.module.scss";

const mockUseConnectionEditService = jest.fn();

jest.doMock("hooks/services/ConnectionEdit/ConnectionEditService", () => ({
  useConnectionEditService: mockUseConnectionEditService,
}));

const mockUseRefreshSourceSchemaWithConfirmationOnDirty = jest.fn();

jest.doMock("views/Connection/ConnectionForm/components/refreshSourceSchemaWithConfirmationOnDirty", () => ({
  useRefreshSourceSchemaWithConfirmationOnDirty: mockUseRefreshSourceSchemaWithConfirmationOnDirty,
}));

jest.mock("hooks/connection/useIsAutoDetectSchemaChangesEnabled", () => ({
  useIsAutoDetectSchemaChangesEnabled: () => true,
}));

// eslint-disable-next-line @typescript-eslint/no-var-requires
const { SchemaChangesDetected } = require("./SchemaChangesDetected");

describe("<SchemaChangesDetected />", () => {
  beforeEach(() => {
    mockUseConnectionEditService.mockReturnValue({
      connection: mockConnection,
      schemaHasBeenRefreshed: false,
      schemaRefreshing: false,
    });
  });

  it("does not render if schema has been refreshed", () => {
    mockUseConnectionEditService.mockReturnValue({
      connection: mockConnection,
      schemaHasBeenRefreshed: true,
      schemaRefreshing: false,
    });

    const { queryByTestId } = render(<SchemaChangesDetected />, { wrapper: TestWrapper });

    expect(queryByTestId("schemaChagnesDetected")).toBeFalsy();
  });

  it("renders with breaking changes", () => {
    mockUseConnectionEditService.mockReturnValue({
      connection: { mockConnection, schemaChange: SchemaChange.breaking },
      schemaHasBeenRefreshed: false,
      schemaRefreshing: false,
    });

    const { getByTestId } = render(<SchemaChangesDetected />, { wrapper: TestWrapper });

    expect(getByTestId("schemaChangesDetected")).toHaveClass(styles.breaking);
    expect(getByTestId("schemaChangesDetected")).not.toHaveClass(styles.nonBreaking);
    expect(getByTestId("schemaChangesDetected")).toHaveTextContent(en["connection.schemaChange.breaking"]);
  });

  it("renders with non-breaking changes", () => {
    mockUseConnectionEditService.mockReturnValue({
      connection: { mockConnection, schemaChange: SchemaChange.non_breaking },
      schemaHasBeenRefreshed: false,
      schemaRefreshing: false,
    });

    const { getByTestId } = render(<SchemaChangesDetected />, { wrapper: TestWrapper });

    expect(getByTestId("schemaChangesDetected")).toHaveClass(styles.nonBreaking);
    expect(getByTestId("schemaChangesDetected")).not.toHaveClass(styles.breaking);
    expect(getByTestId("schemaChangesDetected")).toHaveTextContent(en["connection.schemaChange.nonBreaking"]);
  });

  it("calls refresh schema after review button click", () => {
    mockUseConnectionEditService.mockReturnValue({
      connection: { mockConnection, schemaChange: SchemaChange.non_breaking },
      schemaHasBeenRefreshed: false,
      schemaRefreshing: false,
    });

    const refreshSpy = jest.fn();
    mockUseRefreshSourceSchemaWithConfirmationOnDirty.mockReturnValue(refreshSpy);

    const { getByRole } = render(<SchemaChangesDetected />, { wrapper: TestWrapper });

    userEvent.click(getByRole("button"));

    expect(refreshSpy).toHaveBeenCalled();
  });
});
