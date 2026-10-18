from pathlib import Path
class Position:
    x_pos : int
    y_pos : int
    width : int
    height : int

    def x_right(self) -> float:
        return self.x_pos + self.width

    def y_bottom(self) -> float:
        return self.y_pos + self.height
    
    def contains(self, position: Position) -> bool:
        if self.x_pos <= position.x_pos:
            if self.y_pos <= position.y_pos:
                if self.x_right() >= position.x_right():
                    return self.y_bottom() >= position.y_bottom()
        return False

    def overlap(self, position:Position):
        if self.x_pos >= position.x_right() or self.x_right() <= position.x_pos:
            return False
        return self.y_pos >= position.y_bottom() or self.y_bottom() <= position.y_pos

    def ratio(self):
        return self.width / self.height



class Video_Region:
    def __init__(self, video:Path, pos: Position) -> None:
        self.position = pos
        pass

class Video_Format:
    def __init__(self, projections: list[tuple[Video_Region,Position]], target_region:Position) -> None:
        self.projections = projections
        self.target_region = target_region


def validate(format: Video_Format):
    target = format.target_region
    destinations: list[Position] = []
    result: dict[str,list[str]] = {}
    for i in range(0,len(format.projections)-1):
        result |= {f"projection_{i}":[]}        
        projection = format.projections[i]
        destination = projection[1]
        source = projection[0].position
        if source.ratio() != destination.ratio():
            result["projection_{i}"].append("Source and Destination aspect ratios do not match")
        if not target.contains(destination):
            result["projection_{i}"].append("Video Target does not contain projection destination")
        for j in range(0,len(destinations)-1):
            if destination.overlap(destinations[j]):
                result["projection_{i}"].append(f"Destination overlaps with projection {j}")
        destinations.append(destination)


        
