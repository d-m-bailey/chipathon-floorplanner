from dataclasses import dataclass

@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def area(self): return self.w * self.h

    @property
    def center(self): return self.x + self.w / 2, self.y + self.h / 2

    def intersects(self, other):
        return max(self.x, other.x) < min(self.x+self.w, other.x+other.w) and max(self.y, other.y) < min(self.y+self.h, other.y+other.h)

    def contains(self, other):
        return self.x <= other.x and self.y <= other.y and self.x+self.w >= other.x+other.w and self.y+self.h >= other.y+other.h

    def subtract(self, cut):
        if not self.intersects(cut): return [self]
        x1,y1=max(self.x,cut.x),max(self.y,cut.y)
        x2,y2=min(self.x+self.w,cut.x+cut.w),min(self.y+self.h,cut.y+cut.h)
        return [r for r in [Rect(self.x,self.y,self.w,y1-self.y),Rect(self.x,y2,self.w,self.y+self.h-y2),Rect(self.x,y1,x1-self.x,y2-y1),Rect(x2,y1,self.x+self.w-x2,y2-y1)] if r.w>0 and r.h>0]
