import json
import plotly.graph_objects as go
import numpy as np
from field_model import FieldModel

def plot_elevation():
    # Load data using FieldModel
    field = FieldModel()
    field.load_from_file("auto.json")
    
    # Extract x, y, z values from points
    x_values = []
    y_values = []
    z_values = []
    
    for point in field.points:
        x_values.append(point["x"])
        y_values.append(point["y"])
        z_values.append(point["z"])
    
    # Determine min/max for proper color scaling
    z_min = min(z_values)
    z_max = max(z_values)
    
    # Create a custom colorscale: blue (negative) -> white (zero) -> red (positive)
    # Scale needs to be adjusted to place white at z=0
    z_range = max(abs(z_min), abs(z_max))
    midpoint = 0.5 + (0 - z_min) / (2 * z_range) if z_range > 0 else 0.5
    
    colorscale = [
        [0, 'blue'],
        [midpoint, 'white'],
        [1, 'red']
    ]
    
    # Create the interactive scatter plot
    fig = go.Figure(data=go.Scatter(
        x=x_values,
        y=y_values,
        mode='markers',
        marker=dict(
            size=10,
            color=z_values,
            colorscale=colorscale,
            colorbar=dict(title="Elevation (z)"),
            cmin=z_min,
            cmax=z_max,
            showscale=True
        ),
        hovertemplate='x: %{x:.2f}<br>y: %{y:.2f}<br>z: %{marker.color:.2f}<extra></extra>'
    ))
    
    # Update layout for better visualization
    fig.update_layout(
        title="Field Elevation Visualization",
        xaxis_title="X Position (m)",
        yaxis_title="Y Position (m)",
        hovermode='closest'
    )
    
    # Make axes equal to preserve spatial relationships
    fig.update_layout(
        yaxis=dict(
            scaleanchor="x",
            scaleratio=1,
        )
    )
    
    # Show the plot
    fig.show()

if __name__ == "__main__":
    plot_elevation()