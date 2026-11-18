
import cv2

camera = cv2.VideoCapture(0)

print("摄像头打开状态：", camera.isOpened())

if not camera.isOpened():
    print("摄像头打开失败")
    exit()

print("正在显示测试窗口，按 Q 退出")

while True:
    success, frame = camera.read()

    if not success:
        print("读取画面失败")
        break

    cv2.imshow("Camera Test", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()
